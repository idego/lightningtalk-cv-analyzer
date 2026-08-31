from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

from cv_validator.document_understanding.annotations import build_shared_annotations, project_structural_v1
from cv_validator.document_understanding.contract import sanitize_understanding
from cv_validator.document_understanding.domain import (
    AmbiguousSpan, Confidence, DateRangeAnnotation, DocumentAnnotationIndex,
    DocumentUnderstandingResult, EntrySpan, ResearchSubject, SectionKind, Status,
    StructuredField, StructuredRecord, UnderstandingCoverage,
    UnderstandingEvidence, stable_source_id,
)
from cv_validator.document_understanding.normalization import normalize_text, subject_key
from cv_validator.document_understanding.relationships import is_self_employment_label
from cv_validator.document_understanding.skills import DEFAULT_INDEX, SkillIndexError, match_explicit_skills
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import SourceLine
from cv_validator.location import LocationResolver

PARSER_VERSION = "document-understanding-parser-v1"
RULESET_VERSION = "document-understanding-rules-v1"
_INSTITUTIONS = ("university", "college", "academy", "school", "institute", "faculty", "uniwersytet", "politechnika", "akademia", "szkola", "wydzial")
_DEGREES = ("bachelor", "master", "phd", "doctorate", "licencjat", "magister", "inzynier", "mba", "bsc", "msc")
_ROLES = ("engineer", "developer", "manager", "consultant", "analyst", "designer", "specialist", "architect", "director", "lead", "intern", "programista", "inzynier", "konsultant", "analityk", "specjalista", "kierownik")
_ORG_SUFFIX = re.compile(r"(?i)\b(?:ltd|limited|inc|corp|corporation|llc|gmbh|ag|sa|s\.a\.|sp\.\s*z\s*o\.o\.|labs?|studio|group)\b")
_IDENTITY_CONNECTOR = re.compile(r"(?i)^\s*(?P<role>[^|;\t•—–]{2,80}?)\s+(?P<connector>at|@|[—–]|-{2,}|\|)\s+(?P<organization>[^|;\t•—–]{2,80}?)\s*$")
_WORK_MODE = frozenset({"remote", "hybrid", "onsite", "on-site", "zdalnie", "hybrydowo", "stacjonarnie"})
_DUTY_PREFIX = re.compile(r"(?i)^(?:built|build(?:ing)?|developed|develop(?:ing)?|created|creat(?:e|ing)|managed|manag(?:e|ing)|led|leading|designed|design(?:ing)?|implemented|implement(?:ing)?|maintained|maintain(?:ing)?|responsible\s+for)\b")
_VISIBLE_BULLET_PREFIX = re.compile(r"^\s*(?:[•●▪◦‣⁃]|[-*]\s)")
_MAX_EMPLOYMENT_ENTRY_LINES = 64
_MAX_EMPLOYMENT_ENTRY_CHARS = 8192
_MAX_EMPLOYMENT_CANDIDATES = 32
_MAX_RANKED_CANDIDATES = 8
_LABEL_PREFIX = r"(?:^\s*|[|;]\s*)"
_LABELS = {
    "organization": re.compile(rf"(?i){_LABEL_PREFIX}(?:company|employer|organization|pracodawca|firma)\s*:\s*(?P<value>[^|;]+)"),
    "client": re.compile(rf"(?i){_LABEL_PREFIX}(?:client|klient)\s*:\s*(?P<value>[^|;]+)"),
    "role": re.compile(rf"(?i){_LABEL_PREFIX}(?:role|position|title|stanowisko)\s*:\s*(?P<value>[^|;]+)"),
    "program": re.compile(rf"(?i){_LABEL_PREFIX}(?:program|programme|course|field of study|kierunek)\s*:\s*(?P<value>[^|;]+)"),
    "location": re.compile(rf"(?i){_LABEL_PREFIX}(?:location|lokalizacja|city|miasto)\s*:\s*(?P<value>[^|;]+)"),
    "result": re.compile(rf"(?i){_LABEL_PREFIX}(?:result|grade|wynik|ocena)\s*:\s*(?P<value>[^|;]+)"),
}


@dataclass(frozen=True)
class _EmploymentCandidate:
    page_id: str
    page_number: int
    line_id: str
    text: str
    start_offset: int
    end_offset: int
    source_order: int
    date_side: str | None = None
    bold: bool = False
    font_size: float | None = None
    role_layout_signal: bool = False
    organization_layout_signal: bool = False


def understand_document(document, deterministic_ruleset_version: str, *, snapshot_month: str | None = None, location_resolver: LocationResolver | None = None, small_locality_population_max: int = 10_000, skill_index_path: Path = DEFAULT_INDEX) -> DocumentUnderstandingResult:
    snapshot = snapshot_month or date.today().strftime("%Y-%m")
    snapshot, exclusion, sections, timeline, visibility = build_shared_annotations(document, snapshot_month=snapshot)
    structural = project_structural_v1(document, snapshot, timeline, visibility)
    dates = _dates(structural)
    entries, entry_issues = _entries(document, sections, dates)
    records, field_issues = _records(document, sections, dates, entries, exclusion)
    records = _deduplicate(records)
    try:
        skills = match_explicit_skills(document, sections, exclusion, index_path=skill_index_path)
        skills_available = True
    except SkillIndexError:
        skills = ()
        skills_available = False
    deterministic = analyze_deterministically(document, deterministic_ruleset_version, location_resolver=location_resolver, small_locality_population_max=small_locality_population_max, exclusion_index=exclusion)
    omitted = []
    omitted_map = {
        "docx_headers": "docx_headers", "docx_footers": "docx_footers",
        "docx_textboxes": "docx_textboxes", "docx_comments": "docx_comments",
        "docx_drawings": "docx_drawings", "docx_footnotes": "docx_footnotes_endnotes",
        "docx_endnotes": "docx_footnotes_endnotes", "docx_embedded_files": "docx_embedded_files",
        "pdf_non_text_content": "pdf_non_text_content",
    }
    for part in document.presentation_omitted_parts:
        mapped = omitted_map.get(part)
        if mapped and mapped not in omitted: omitted.append(mapped)
    if document.source_blocks_partial: omitted.append("source_blocks_unavailable")
    if exclusion.partial_coverage: omitted.append("presentation_spans_unavailable")
    if not skills_available: omitted.append("skills_unavailable")
    # Quarantined presentation evidence is intentionally excluded from every
    # downstream collection.  The visible projection is therefore honest but
    # necessarily partial even when the extraction adapter covered the file.
    status = Status.PARTIAL if omitted or exclusion.intervals else Status.COMPLETED
    audited = ["canonical_pages", "source_blocks", "presentation_spans", "section_annotations", "date_annotations", "entry_annotations"]
    if skills_available: audited.append("skill_taxonomy")
    coverage = UnderstandingCoverage(status, document.source_format, tuple(audited), tuple(omitted))
    issues = tuple(sorted((*entry_issues, *field_issues), key=lambda item: (item.source_order, item.id)))
    return DocumentUnderstandingResult(document, DocumentAnnotationIndex(exclusion.intervals, sections, dates), deterministic, structural, sections, dates, records, skills, issues, _timeline_links(records, dates), _subjects(records), coverage, snapshot)


def understanding_to_payload(result: DocumentUnderstandingResult) -> dict:
    def ev(e): return {"page_id": e.page_id, "page_number": e.page_number, "line_id": e.line_id, "start_offset": e.start_offset, "end_offset": e.end_offset, "association": e.association, "excerpt": e.excerpt}
    sections=[{"id":x.id,"kind":x.kind.value,"confidence":x.confidence.value,"heading":x.heading[:128],"start_line_id":x.start_line_id,"end_line_id":x.end_line_id,"evidence":[ev(e) for e in x.evidence]} for x in result.sections]
    dates=[{"id":x.id,"source_literal":x.source_literal[:128],"start_month":x.start_month,"end_month":x.end_month,"start_precision":x.start_precision,"end_precision":x.end_precision,"status":x.status,"snapshot_month":x.snapshot_month,"evidence":[ev(e) for e in x.evidence]} for x in result.date_ranges]
    records=[{"id":x.id,"kind":x.kind,"section_id":x.section_id,"confidence":x.confidence.value,"fields":[{"name":f.name,"status":f.status,"value":f.value,"authority":"code","confidence":f.confidence.value,"evidence":[ev(e) for e in f.evidence]} for f in x.fields],"date_range_ids":list(x.date_range_ids)} for x in result.records]
    ambiguous=[{"id":x.id,"category":x.category,"reason_code":x.reason_code,"evidence":[ev(e) for e in x.evidence]} for x in result.ambiguous_spans]
    subjects=[{"id":x.id,"category":x.category,"subject":x.subject,"record_id":x.record_id,"field_name":x.field_name} for x in result.code_research_subjects]
    skills=[{"id":x.id,"canonical_id":x.canonical_id,"display_label":x.display_label,"taxonomy":"esco","taxonomy_version":x.taxonomy_version,"confidence":x.confidence.value,"evidence":[ev(e) for e in x.evidence]} for x in result.skills]
    collections={"sections":sections,"date_ranges":dates,"records":records,"skills":skills,"ambiguous_spans":ambiguous,"timeline_record_links":[dict(x) for x in result.timeline_record_links],"code_research_subjects":subjects}
    payload={"contract_version":"document-understanding-v1","status":result.coverage.status.value,"parser_version":result.parser_version,"ruleset_version":result.ruleset_version,"snapshot_month":result.snapshot_month,"coverage":{"status":result.coverage.status.value,"source_format":result.coverage.source_format,"audited_parts":list(result.coverage.audited_parts),"omitted_parts":list(result.coverage.omitted_parts)},**collections,"truncation":{name:{"reported_count":len(values),"additional_count":0,"truncated":False} for name,values in collections.items()}}
    sanitized=sanitize_understanding(payload,timeline_entry_ids={entry.id for entry in result.structural_audits.timeline.entries})
    if sanitized is None: raise ValueError("document understanding unexpectedly null")
    return sanitized


def _dates(structural):
    result=[]
    for order,entry in enumerate(structural.timeline.entries):
        loc=entry.source_location; literal=entry.evidence[0].excerpt if entry.evidence else ""
        evidence=UnderstandingEvidence(loc.page_id,loc.page_number,loc.line_id,loc.start_offset,loc.end_offset,loc.association.value,literal)
        result.append(DateRangeAnnotation(stable_source_id("date-range",loc.page_id,loc.start_offset or 0,loc.end_offset or 0),literal,entry.start_month,entry.end_month,entry.start_precision,entry.end_precision,entry.status,structural.snapshot_month or "",(evidence,),order,entry.id))
    return tuple(result)


def _entries(document, sections, dates):
    line_order={line.line_id:i for i,line in enumerate(document.source_lines)}; dates_by_line={}
    for item in dates:
        if item.evidence and item.evidence[0].line_id: dates_by_line.setdefault(item.evidence[0].line_id,[]).append(item)
    result=[]; issues=[]
    for section in sections:
        if section.kind not in {SectionKind.EDUCATION,SectionKind.EMPLOYMENT}: continue
        start,end=line_order[section.start_line_id],line_order[section.end_line_id]
        blocks=[b for b in document.source_blocks if b.line_ids and any(start < line_order.get(line_id,-1) <= end for line_id in b.line_ids)]
        current=[]; anchors=[]; table=None; row=None; anchor_first=False; anchor_block_index=None
        for block in blocks:
            row_boundary=current and block.table_id is not None and table==block.table_id and row is not None and block.row_index!=row
            found=[d for line_id in block.line_ids for d in dates_by_line.get(line_id,())]
            if current and row_boundary:
                result.append(_entry(section.id,current,anchors,len(result))); current=[]; anchors=[]; anchor_first=False; anchor_block_index=None
            if current and found and anchors:
                if anchor_first:
                    result.append(_entry(section.id,current,anchors,len(result))); current=[]; anchors=[]; anchor_first=False; anchor_block_index=None
                else:
                    split_at=(_next_education_identity_start if section.kind is SectionKind.EDUCATION else _next_employment_identity_start)(document,(*current,block),(anchor_block_index or 0)+1)
                    if split_at is not None:
                        result.append(_entry(section.id,current[:split_at],anchors,len(result)))
                        current=current[split_at:]; anchors=[]; anchor_first=False; anchor_block_index=None
            non_date_before=bool(current)
            current.append(block); table,row=block.table_id,block.row_index
            anchors.extend(d for d in found if d.id not in {x.id for x in anchors})
            if found:
                if not non_date_before: anchor_first=True
                if anchor_block_index is None: anchor_block_index=len(current)-1
            if len(anchors)>1: issues.extend(_ambiguous_from_evidence(anchors[0].evidence,"multiple_date_anchors",block.source_order))
        if current: result.append(_entry(section.id,current,anchors,len(result)))
    unique_issues={issue.id:issue for issue in issues}
    return tuple(result),tuple(unique_issues.values())


def _next_employment_identity_start(document, blocks, start):
    lookup={line.line_id:line for line in document.source_lines}; hints=[]
    for index,block in enumerate(blocks[start:],start):
        lines=[lookup[line_id] for line_id in block.line_ids if line_id in lookup]
        text=_strip_visible_bullet(" ".join(line.text.strip() for line in lines).strip())
        if not text or _DUTY_PREFIX.search(text):continue
        without_dates=_strip_date_ranges(text)
        if without_dates and (any(pattern.search(without_dates) for pattern in (_LABELS["organization"],_LABELS["role"])) or _looks_org(without_dates) or _has_role_marker(without_dates) or _IDENTITY_CONNECTOR.match(without_dates)):
            hints.append(index)
    if not hints:return None
    identity_index=hints[-1]
    if identity_index>start:
        previous=blocks[identity_index-1]; lines=[lookup[line_id] for line_id in previous.line_ids if line_id in lookup]
        text=_strip_visible_bullet(" ".join(line.text.strip() for line in lines).strip())
        if text and not _DUTY_PREFIX.search(text):identity_index-=1
    return identity_index


def _next_education_identity_start(document, blocks, start):
    lookup={line.line_id:line for line in document.source_lines}
    for index,block in enumerate(blocks[start:],start):
        lines=[lookup[line_id] for line_id in block.line_ids if line_id in lookup]
        if any(marker in normalize_text(_strip_date_ranges(line.text)) for line in lines for marker in _INSTITUTIONS):return index
    return None


def _strip_visible_bullet(value):
    return _VISIBLE_BULLET_PREFIX.sub("",value,1).strip()


def _strip_date_ranges(value):
    # Structural date evidence supplies the exact ownership later. This helper
    # only decides whether the same block also contains an identity fragment.
    return re.sub(r"(?i)(?:[a-ząćęłńóśźż]{3,12}\.?\s+)?\d{4}\s*(?:[-–—]|\bto\b)\s*(?:(?:[a-ząćęłńóśźż]{3,12}\.?\s+)?\d{4}|present|current|now|obecnie|teraz)","",value).strip(" |,;:–—-")


def _entry(section_id,blocks,dates,order):
    first,last=blocks[0],blocks[-1]
    return EntrySpan(stable_source_id("entry",first.page_id,first.start_offset or 0,last.end_offset or first.end_offset or 0),section_id,tuple(b.id for b in blocks),tuple(d.id for d in dates[:4]),order)


def _records(document,sections,dates,entries,exclusion):
    section_by_id={x.id:x for x in sections}; block_by_id={x.id:x for x in document.source_blocks}; date_by_id={x.id:x for x in dates}; records=[]; issues=[]
    for entry in entries:
        entry_blocks=[block_by_id[x] for x in entry.block_ids]; lines=_lines(document,entry_blocks); entry_dates=[date_by_id[x] for x in entry.date_range_ids]
        if not lines: continue
        if section_by_id[entry.section_id].kind is SectionKind.EDUCATION: record,new_issues=_education(document,section_by_id[entry.section_id],entry,lines,entry_dates,exclusion)
        else: record,new_issues=_employment(document,section_by_id[entry.section_id],entry,lines,entry_dates,exclusion,entry_blocks)
        issues.extend(new_issues)
        if record: records.append(record)
    return tuple(records),tuple(issues)


def _education(document,section,entry,lines,dates,exclusion):
    candidates=_education_candidates(document,lines,dates)
    identity=_unique(candidates,lambda s:any(m in normalize_text(s) for m in _INSTITUTIONS)); degree=_unique(candidates,lambda s:any(m in normalize_text(s) for m in _DEGREES)); program=_label(lines,"program")
    if identity is not None and degree is identity and program is None:
        return None,_issue(document,lines,"unsupported_education_identity",entry.source_order,exclusion)
    if identity is None: return None,_issue(document,lines,"unsupported_education_identity",entry.source_order,exclusion)
    institution=_field(document,"institution",identity,exclusion)
    if institution.status!="supported" or not (degree or program or dates): return None,_issue(document,lines,"insufficient_education_support",entry.source_order,exclusion)
    fields=(institution,_field(document,"program",program,exclusion),_field(document,"degree",degree,exclusion),_date_field("study_dates",dates),_field(document,"result",_label(lines,"result"),exclusion),_field(document,"education_location",_label(lines,"location"),exclusion))
    return _record("education",section,entry,lines,fields,dates),()


def _employment(document,section,entry,lines,dates,exclusion,blocks):
    relationship=_unique(lines,is_self_employment_label); role=_label(lines,"role"); client=_label(lines,"client"); organization=_label(lines,"organization")
    issues=();truncated=False
    if len(dates)>1:return None,issues
    # Unlabelled layout inference is anchored to a shared date annotation.  This
    # prevents descriptive text in an employment section from becoming a record
    # merely because two short, styled fragments happen to be adjacent.
    if dates:
        candidates,truncated=_employment_candidates(document,lines,dates,exclusion,excluded={relationship,client,_label(lines,"location")})
        if truncated:
            issues=_issue(document,lines,"employment_candidate_limit",entry.source_order,exclusion)
        else:
            role,organization=_pair_employment_candidates(candidates,role,organization)
    if client and organization is None:
        issues=(*issues,*_issue(document,(client,),"employer_client_ambiguity",entry.source_order,exclusion))
    org_field=_field(document,"organization",organization,exclusion); rel_field=_field(document,"relationship_type",relationship,exclusion); role_field=_field(document,"role",role,exclusion)
    if truncated and org_field.status!="supported" and rel_field.status!="supported":return None,issues
    if org_field.status!="supported" and rel_field.status!="supported": return None,(*issues,*_issue(document,lines,"unsupported_employment_identity",entry.source_order,exclusion))
    if role_field.status!="supported" and not dates: return None,(*issues,*_issue(document,lines,"insufficient_employment_support",entry.source_order,exclusion))
    fields=(org_field,role_field,rel_field,_date_field("employment_dates",dates),_field(document,"employment_location",_label(lines,"location"),exclusion))
    return _record("employment",section,entry,lines,fields,dates),issues


def _record(kind,section,entry,lines,fields,dates):
    return StructuredRecord(stable_source_id(f"record-{kind}",lines[0].page_id,lines[0].start_offset,lines[-1].end_offset),kind,section.id,Confidence.HIGH,tuple(fields),tuple(d.id for d in dates),entry.source_order)


def _lines(document,blocks):
    lookup={x.line_id:x for x in document.source_lines}; seen=set(); result=[]
    for block in blocks:
        for line_id in block.line_ids:
            if line_id not in seen and line_id in lookup and lookup[line_id].text.strip(): seen.add(line_id); result.append(lookup[line_id])
    return result


def _unique(lines,predicate):
    values=[line for line in lines if predicate(line.text.strip())]; return values[0] if len(values)==1 else None
def _label(lines,name):
    values=[line for line in lines if _LABELS[name].search(line.text)]; return values[0] if len(values)==1 else None
def _has_date(line,dates): return any(d.evidence and d.evidence[0].line_id==line.line_id for d in dates)
def _looks_org(value):
    text=value.strip(); words=text.split()
    return not is_self_employment_label(text) and not _LABELS["client"].search(text) and bool(_ORG_SUFFIX.search(text))


def _employment_candidates(document,lines,dates,exclusion,excluded):
    if len(lines)>_MAX_EMPLOYMENT_ENTRY_LINES or sum(len(line.text) for line in lines)>_MAX_EMPLOYMENT_ENTRY_CHARS:
        return (),True
    line_order={line.line_id:index for index,line in enumerate(lines)}
    presentation_by_line=_presentation_by_line(document,lines)
    date_intervals={}
    for item in dates:
        for evidence in item.evidence:
            if evidence.line_id and evidence.start_offset is not None and evidence.end_offset is not None:
                date_intervals.setdefault(evidence.line_id,[]).append((evidence.start_offset,evidence.end_offset))
    result=[]
    for line in lines:
        if line in excluded or any(pattern.search(line.text) for pattern in _LABELS.values()):
            continue
        intervals=sorted(date_intervals.get(line.line_id,()))
        line_presentation=presentation_by_line.get(line.line_id,())
        spans=[]
        if intervals:
            cursor=line.start_offset
            for start,end in intervals:
                if cursor<start:spans.extend(_candidate_fragments(document,line,cursor,start,"before",line_presentation))
                cursor=max(cursor,end)
            if cursor<line.end_offset:spans.extend(_candidate_fragments(document,line,cursor,line.end_offset,"after",line_presentation))
        else:
            spans.extend(_candidate_fragments(document,line,line.start_offset,line.end_offset,None,line_presentation))
        for start,end,value,date_side,role_layout,organization_layout in spans:
            normalized=normalize_text(value); words=value.split()
            if not normalized or len(value)>110 or len(words)>12 or len(words)>0 and len(words)==1 and not any(ch.isalpha() for ch in value):continue
            if _DUTY_PREFIX.search(value):continue
            if any(marker in normalized for marker in _INSTITUTIONS) or is_self_employment_label(value):continue
            if re.search(r"(?i)(?:https?://|www\.|@|\+?\d[\d ()./-]{6,})",value):continue
            if value.rstrip().endswith((".",";")) and len(words)>5:continue
            if exclusion.intersects(line.page_id,start,end):continue
            presentation=[span for span in presentation_by_line.get(line.line_id,()) if span.start_offset<end and start<span.end_offset]
            bold_chars=sum(max(0,min(end,span.end_offset)-max(start,span.start_offset)) for span in presentation if span.bold)
            sizes=[span.font_size_points for span in presentation if span.font_size_points is not None]
            page=next(page for page in document.pages if page.page_id==line.page_id)
            role_layout=role_layout or _has_role_marker(value)
            result.append(_EmploymentCandidate(line.page_id,page.page_number,line.line_id,value,start,end,line_order[line.line_id],date_side,bold_chars>=max(1,(end-start)//2),max(sizes) if sizes else None,role_layout,organization_layout))
            if len(result)>_MAX_EMPLOYMENT_CANDIDATES:return (),True
    unique={}
    for candidate in result:
        key=(candidate.page_id,candidate.start_offset,candidate.end_offset)
        previous=unique.get(key)
        unique[key]=replace(candidate,role_layout_signal=candidate.role_layout_signal or bool(previous and previous.role_layout_signal),organization_layout_signal=candidate.organization_layout_signal or bool(previous and previous.organization_layout_signal))
    candidates=tuple(sorted(unique.values(),key=lambda item:(item.source_order,item.start_offset,item.end_offset)))
    return _sequence_layout_signals(candidates,date_intervals,line_order),False


def _education_candidates(document,lines,dates):
    date_intervals={}
    for item in dates:
        for evidence in item.evidence:
            if evidence.line_id and evidence.start_offset is not None and evidence.end_offset is not None:
                date_intervals.setdefault(evidence.line_id,[]).append((evidence.start_offset,evidence.end_offset))
    presentation_by_line=_presentation_by_line(document,lines); result=[]
    for line in lines:
        intervals=sorted(date_intervals.get(line.line_id,())); spans=[]; cursor=line.start_offset
        for start,end in intervals:
            if cursor<start:spans.extend(_candidate_fragments(document,line,cursor,start,"before",presentation_by_line.get(line.line_id,())))
            cursor=max(cursor,end)
        if cursor<line.end_offset:spans.extend(_candidate_fragments(document,line,cursor,line.end_offset,"after" if intervals else None,presentation_by_line.get(line.line_id,())))
        for start,end,value,*_ in spans:
            if not value or len(value)>256 or _VISIBLE_BULLET_PREFIX.match(value):continue
            result.append(SourceLine(line.page_id,line.line_number,value,start,end))
    unique={(line.page_id,line.start_offset,line.end_offset):line for line in result}
    return tuple(sorted(unique.values(),key=lambda line:(line.page_id,line.start_offset,line.end_offset)))


def _presentation_by_line(document,lines):
    by_page={}
    for span in document.presentation_spans:
        if span.start_offset is not None and span.end_offset is not None:
            by_page.setdefault(span.page_id,[]).append(span)
    result={}
    for line in lines:
        result[line.line_id]=tuple(span for span in by_page.get(line.page_id,()) if span.start_offset<line.end_offset and line.start_offset<span.end_offset)
    return result


def _candidate_fragments(document,line,start,end,date_side,presentation_spans=()):
    page=next(page for page in document.pages if page.page_id==line.page_id)
    raw=page.text[start:end]
    base=start
    result=[]
    for match in re.finditer(r"[^|;\t•]+",raw):
        value=match.group().strip(" ,:–—-\u00a0")
        if not value:continue
        relative=match.start()+match.group().find(value)
        result.append((base+relative,base+relative+len(value),value,date_side,False,False))
    connector=_IDENTITY_CONNECTOR.match(raw.strip(" ,:–—-\u00a0"))
    if connector and _has_role_marker(connector.group("role")) and not _inadmissible_organization_fragment(connector.group("organization")):
        stripped=raw.strip(" ,:–—-\u00a0"); stripped_offset=raw.find(stripped)
        for group in ("role","organization"):
            value=connector.group(group).strip(); relative=stripped_offset+connector.start(group)+connector.group(group).find(value)
            result.append((base+relative,base+relative+len(value),value,date_side,group=="role",group=="organization"))
    styled=[]
    presentation=sorted((span for span in presentation_spans if start<span.end_offset and span.start_offset<end),key=lambda span:(span.start_offset or 0,span.end_offset or 0))
    for span in presentation:
        left=max(start,span.start_offset or start);right=min(end,span.end_offset or end)
        if left>=right:continue
        signature=(span.bold,span.font_size_points)
        if styled and styled[-1][3]==signature and left<=styled[-1][1]+1:
            styled[-1]=(styled[-1][0],right,page.text[styled[-1][0]:right],signature)
        else:styled.append((left,right,page.text[left:right],signature))
    meaningful=[]
    for left,right,value,_ in styled:
        cleaned=value.strip(" |;,:–—-\u00a0")
        if not cleaned or not any(ch.isalpha() for ch in cleaned):continue
        relative=value.find(cleaned);meaningful.append((left+relative,left+relative+len(cleaned),cleaned,date_side,False,False))
    if 2<=len(meaningful)<=4:
        # A paragraph whose runs deliberately change emphasis carries its own
        # field boundaries.  Do not retain a larger fragment that merely wraps
        # multiple styled fields, because that creates a duplicate composite
        # employer/role candidate.
        result=[fragment for fragment in result if not sum(fragment[0]<=part[0] and part[1]<=fragment[1] for part in meaningful)>=2]
        result.extend(meaningful)
    return result


def _has_role_marker(value):
    normalized=normalize_text(value)
    return any(marker in normalized for marker in _ROLES)


def _inadmissible_organization_fragment(value):
    normalized=normalize_text(value)
    return normalized in _WORK_MODE or bool(_DUTY_PREFIX.search(value.strip()))


def _sequence_layout_signals(candidates,date_intervals,line_order):
    date_orders=sorted({line_order[line_id] for line_id in date_intervals if line_id in line_order})
    role_candidates=[candidate for candidate in candidates if candidate.role_layout_signal]
    if len(role_candidates)>1:
        emphasized=[candidate for candidate in role_candidates if candidate.bold]
        if len(emphasized)==1:role_candidates=emphasized
    if len(role_candidates)!=1 or not date_orders:return candidates
    role=role_candidates[0];ordered=list(candidates);role_index=ordered.index(role);marked=[]
    preceding=ordered[role_index-1] if role_index else None
    following=ordered[role_index+1] if role_index+1<len(ordered) else None
    for candidate in candidates:
        organization_signal=candidate.organization_layout_signal
        if candidate is not role and not _inadmissible_organization_fragment(candidate.text):
            organization_signal=organization_signal or any(
                candidate is preceding and (
                    date_order<candidate.source_order<=role.source_order
                    or candidate.source_order<=role.source_order<date_order
                )
                or candidate.line_id==role.line_id and candidate in {preceding,following}
                or candidate is following and (
                    candidate.date_side is not None
                    or candidate.bold and candidate.font_size!=role.font_size
                )
                for date_order in date_orders
            )
        marked.append(replace(candidate,organization_layout_signal=organization_signal))
    return tuple(marked)


def _pair_employment_candidates(candidates,role,organization):
    if not candidates:return role,organization
    sizes=[item.font_size for item in candidates if item.font_size is not None]
    max_size=max(sizes,default=0)
    has_size_hierarchy=bool(sizes) and max_size-min(sizes)>=1.0
    def role_score(item):
        normalized=normalize_text(item.text)
        return (4 if item.role_layout_signal or any(marker in normalized for marker in _ROLES) else 0)+(2 if item.bold else 0)+(2 if has_size_hierarchy and item.font_size==max_size else 0)+(1 if item.date_side is None else 0)+(1 if len(item.text.split())<=6 else 0)
    def org_score(item):
        normalized=normalize_text(item.text)
        role_like=any(marker in normalized for marker in _ROLES)
        positive=_looks_org(item.text) or item.organization_layout_signal
        return (6 if positive else 0)+(2 if item.date_side and positive else 0)+(1 if item.bold and positive else 0)+(1 if len(item.text.split())<=5 and positive else 0)-(4 if role_like and not _looks_org(item.text) else 0)
    if role is not None:
        ranked=sorted(candidates,key=lambda item:(org_score(item),-item.source_order),reverse=True)
        if organization is None and ranked and org_score(ranked[0])>=6:organization=ranked[0]
        return role,organization
    if organization is not None:
        ranked=sorted(candidates,key=lambda item:(role_score(item),item.source_order),reverse=True)
        if ranked and role_score(ranked[0])>=3:role=ranked[0]
        return role,organization
    strongest_organizations=[item for item in candidates if org_score(item)==max(org_score(candidate) for candidate in candidates)]
    distinct_strongest={normalize_text(item.text) for item in strongest_organizations}
    if len(distinct_strongest)>1 and org_score(strongest_organizations[0])>=6:
        return None,None
    role_candidates=sorted(candidates,key=lambda item:(role_score(item),-item.source_order,-item.start_offset),reverse=True)[:_MAX_RANKED_CANDIDATES]
    org_candidates=sorted((item for item in candidates if org_score(item)>=6),key=lambda item:(org_score(item),-item.source_order,-item.start_offset),reverse=True)[:_MAX_RANKED_CANDIDATES]
    best=None; tied=False
    for role_candidate in role_candidates:
        for org_candidate in org_candidates:
            if role_candidate is org_candidate:continue
            rs,os=role_score(role_candidate),org_score(org_candidate)
            if rs<4:continue
            same_line=int(role_candidate.line_id==org_candidate.line_id)
            gap=min(abs(role_candidate.start_offset-org_candidate.end_offset),abs(org_candidate.start_offset-role_candidate.end_offset))
            current=(rs+os,rs,os,same_line,-abs(role_candidate.source_order-org_candidate.source_order),-gap,role_candidate,org_candidate)
            if best is None or current[:6]>best[:6]:best=current;tied=False
            elif current[:6]==best[:6] and (current[6],current[7])!=(best[6],best[7]):tied=True
    if best is None or tied:return None,None
    return best[6],best[7]


def _field(document,name,line,exclusion):
    if line is None: return StructuredField(name,"unknown",None,Confidence.LOW,())
    label_kind = {"organization":"organization", "role":"role", "program":"program", "result":"result", "education_location":"location", "employment_location":"location"}.get(name)
    label_match = _LABELS[label_kind].search(line.text) if label_kind else None
    if label_match:
        value_start, value_end = label_match.span("value")
        label_start = label_match.start()
        while label_start < value_start and line.text[label_start] in "|; \t": label_start += 1
        label_end = line.start_offset + value_start
        if exclusion.intersects(line.page_id, line.start_offset + label_start, label_end):
            return StructuredField(name,"unknown",None,Confidence.LOW,())
        raw_value=label_match.group("value")
        value=raw_value.strip()
        value_relative=value_start + raw_value.find(value)
        page=next(p for p in document.pages if p.page_id==line.page_id)
        evidence=UnderstandingEvidence(line.page_id,page.page_number,line.line_id,line.start_offset+value_relative,line.start_offset+value_relative+len(value),"exact",value[:256])
    else:
        value,evidence=_value_evidence(document,line)
    if exclusion.intersects(evidence.page_id,evidence.start_offset or 0,evidence.end_offset or 0): return StructuredField(name,"unknown",None,Confidence.LOW,())
    field_evidence = (evidence,)
    if label_match:
        page=next(p for p in document.pages if p.page_id==line.page_id)
        label_text=line.text[label_start:value_start].rstrip(" :\t")
        label_relative=label_start
        label_evidence=UnderstandingEvidence(
            line.page_id,page.page_number,line.line_id,
            line.start_offset+label_relative,
            line.start_offset+label_relative+len(label_text),"exact",label_text[:256],
        )
        field_evidence=(label_evidence,evidence)
    return StructuredField(name,"supported",value[:256],Confidence.HIGH,field_evidence)


def _date_field(name,dates):
    if not dates:return StructuredField(name,"unknown",None,Confidence.LOW,())
    return StructuredField(name,"supported",dates[0].source_literal[:256],Confidence.HIGH,dates[0].evidence[:4])


def _value_evidence(document,line):
    raw=line.text; value=raw.strip(); match=re.match(r"^[^:]{1,40}:\s*(?P<value>.+)$",value)
    if match:value=match.group("value").strip()
    relative=raw.find(value); page=next(p for p in document.pages if p.page_id==line.page_id)
    return value,UnderstandingEvidence(line.page_id,page.page_number,line.line_id,line.start_offset+relative,line.start_offset+relative+len(value),"exact",value[:256])


def _issue(document,lines,reason,order,exclusion=None):
    if not lines:return ()
    selected=tuple(line for line in lines[:4] if line is not None)
    if exclusion is not None:
        # A labelled ownership field is atomic for quarantine purposes.  If
        # either its label or value is excluded, no excerpt from that line may
        # be repackaged as ambiguous evidence.
        selected=tuple(line for line in selected if not exclusion.intersects(line.page_id,line.start_offset,line.end_offset))
    evidence=tuple(_value_evidence(document,line)[1] for line in selected)
    return _ambiguous_from_evidence(evidence,reason,order)
def _ambiguous_from_evidence(evidence,reason,order):
    if not evidence:return ()
    first,last=evidence[0],evidence[-1]
    return (AmbiguousSpan(stable_source_id("ambiguous-entry",first.page_id,first.start_offset or 0,last.end_offset or 0),"entry",reason,tuple(evidence[:4]),order),)


def _deduplicate(records):
    seen=set(); result=[]
    for record in sorted(records,key=lambda x:(x.source_order,x.id)):
        if record.id not in seen:seen.add(record.id);result.append(record)
    return tuple(result)


def _subjects(records):
    seen=set();result=[]
    for record in records:
        name="institution" if record.kind=="education" else "organization";category="education" if record.kind=="education" else "company";field=next((f for f in record.fields if f.name==name and f.status=="supported" and f.value),None)
        if field is None or is_self_employment_label(field.value):continue
        key=subject_key(category,field.value)
        if key in seen:continue
        seen.add(key);e=field.evidence[0];result.append(ResearchSubject(stable_source_id(f"research-{category}",e.page_id,e.start_offset or 0,e.end_offset or 0),category,field.value,record.id,name,record.source_order))
    return tuple(result[:50])


def _timeline_links(records,dates):
    by_date={}
    for record in records:
        for date_id in record.date_range_ids:by_date.setdefault(date_id,[]).append(record)
    return tuple({"timeline_entry_id":d.timeline_entry_id,"record_id":by_date[d.id][0].id} for d in dates if len(by_date.get(d.id,()))==1)
