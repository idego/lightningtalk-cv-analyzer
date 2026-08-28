from __future__ import annotations

from dataclasses import asdict
from datetime import date

from cv_validator.document_understanding.contract import sanitize_understanding
from cv_validator.document_understanding.domain import (
    Confidence, DateRangeAnnotation, DocumentAnnotationIndex,
    DocumentUnderstandingResult, ResearchSubject, SectionKind, SectionSpan,
    Status, StructuredField, StructuredRecord, UnderstandingCoverage,
    UnderstandingEvidence, stable_source_id,
)
from cv_validator.document_understanding.normalization import normalize_text, subject_key
from cv_validator.document_understanding.visibility import build_visibility_exclusion_index
from cv_validator.extraction.deterministic import analyze_deterministically
from cv_validator.ingestion import RedactedDocument, SourceLine
from cv_validator.location import LocationResolver
from cv_validator.document_understanding.structural_projection import annotate_structural_surfaces, project_structural_v1

PARSER_VERSION = "document-understanding-parser-v1"
RULESET_VERSION = "document-understanding-rules-v1"

SECTION_ALIASES = {
    SectionKind.CONTACT: {"contact", "contact details", "kontakt", "dane kontaktowe"},
    SectionKind.SUMMARY: {"summary", "profile", "professional summary", "podsumowanie", "profil zawodowy"},
    SectionKind.EMPLOYMENT: {"experience", "work experience", "employment", "professional experience", "doswiadczenie", "doswiadczenie zawodowe", "zatrudnienie"},
    SectionKind.EDUCATION: {"education", "academic background", "wyksztalcenie", "edukacja"},
    SectionKind.SKILLS: {"skills", "technical skills", "umiejetnosci", "kompetencje"},
    SectionKind.CERTIFICATIONS: {"certifications", "certificates", "certyfikaty"},
    SectionKind.PROJECTS: {"projects", "projekty"},
    SectionKind.LANGUAGES: {"languages", "jezyki"},
    SectionKind.PUBLICATIONS: {"publications", "publikacje"},
    SectionKind.AWARDS: {"awards", "honors", "nagrody", "wyroznienia"},
    SectionKind.VOLUNTEERING: {"volunteering", "volunteer experience", "wolontariat"},
    SectionKind.REFERENCES: {"references", "referencje"},
}
_RELATIONSHIPS = {"freelance", "freelancer", "self employed", "self-employed", "samozatrudnienie", "wolny strzelec"}
_INSTITUTION_MARKERS = ("university", "college", "academy", "school", "institute", "universytet", "uniwersytet", "politechnika", "akademia", "szkola")
_DEGREE_MARKERS = ("bachelor", "master", "phd", "engineer", "licencjat", "magister", "inzynier", "mba", "bsc", "msc")
_ROLE_MARKERS = ("engineer", "developer", "manager", "consultant", "analyst", "designer", "specialist", "architect", "director", "lead", "intern", "programista", "inzynier", "konsultant", "analityk", "specjalista", "kierownik")


def understand_document(
    document: RedactedDocument,
    deterministic_ruleset_version: str,
    *,
    snapshot_month: str | None = None,
    location_resolver: LocationResolver | None = None,
    small_locality_population_max: int = 10_000,
) -> DocumentUnderstandingResult:
    snapshot = snapshot_month or date.today().strftime("%Y-%m")
    exclusion = build_visibility_exclusion_index(document)
    sections = _sections(document, exclusion)
    timeline, visibility = annotate_structural_surfaces(document, snapshot)
    structural = project_structural_v1(document, snapshot, timeline, visibility)
    date_ranges = _dates(structural)
    records = _records(document, sections, date_ranges, exclusion)
    subjects = _subjects(records)
    deterministic = analyze_deterministically(
        document, deterministic_ruleset_version,
        location_resolver=location_resolver,
        small_locality_population_max=small_locality_population_max,
        exclusion_index=exclusion,
    )
    omitted = []
    if document.source_blocks_partial: omitted.append("source_blocks_unavailable")
    if exclusion.partial_coverage: omitted.append("presentation_spans_unavailable")
    status = Status.PARTIAL if omitted else Status.COMPLETED
    coverage = UnderstandingCoverage(
        status=status, source_format=document.source_format,
        audited_parts=("canonical_pages", "source_blocks", "presentation_spans", "section_annotations", "date_annotations", "entry_annotations"),
        omitted_parts=tuple(omitted),
    )
    return DocumentUnderstandingResult(
        document=document,
        annotation_index=DocumentAnnotationIndex(exclusion.intervals, sections, date_ranges),
        deterministic=deterministic, structural_audits=structural,
        sections=sections, date_ranges=date_ranges, records=records,
        skills=(), ambiguous_spans=(), timeline_record_links=_timeline_links(records, date_ranges, structural),
        code_research_subjects=subjects, coverage=coverage, snapshot_month=snapshot,
    )


def understanding_to_payload(result: DocumentUnderstandingResult) -> dict:
    def evidence(value): return {"page_id": value.page_id, "page_number": value.page_number, "line_id": value.line_id, "start_offset": value.start_offset, "end_offset": value.end_offset, "association": value.association, "excerpt": value.excerpt}
    sections = [{"id": x.id, "kind": x.kind.value, "confidence": x.confidence.value, "heading": x.heading[:128], "start_line_id": x.start_line_id, "end_line_id": x.end_line_id, "evidence": [evidence(e) for e in x.evidence]} for x in result.sections]
    dates = [{"id": x.id, "source_literal": x.source_literal[:128], "start_month": x.start_month, "end_month": x.end_month, "start_precision": x.start_precision, "end_precision": x.end_precision, "status": x.status, "snapshot_month": x.snapshot_month, "evidence": [evidence(e) for e in x.evidence]} for x in result.date_ranges]
    records = [{"id": x.id, "kind": x.kind, "section_id": x.section_id, "confidence": x.confidence.value, "fields": [{"name": f.name, "status": f.status, "value": f.value, "authority": "code", "confidence": f.confidence.value, "evidence": [evidence(e) for e in f.evidence]} for f in x.fields], "date_range_ids": list(x.date_range_ids)} for x in result.records]
    subjects = [{"id": x.id, "category": x.category, "subject": x.subject, "record_id": x.record_id, "field_name": x.field_name} for x in result.code_research_subjects]
    names = ("sections", "date_ranges", "records", "skills", "ambiguous_spans", "timeline_record_links", "code_research_subjects")
    payload = {
        "contract_version": "document-understanding-v1", "status": result.coverage.status.value,
        "parser_version": result.parser_version, "ruleset_version": result.ruleset_version,
        "snapshot_month": result.snapshot_month,
        "coverage": {"status": result.coverage.status.value, "source_format": result.coverage.source_format, "audited_parts": list(result.coverage.audited_parts), "omitted_parts": list(result.coverage.omitted_parts)},
        "sections": sections, "date_ranges": dates, "records": records, "skills": [], "ambiguous_spans": [],
        "timeline_record_links": [dict(x) for x in result.timeline_record_links], "code_research_subjects": subjects,
        "truncation": {name: {"reported_count": len(locals_map), "additional_count": 0, "truncated": False} for name, locals_map in (("sections", sections), ("date_ranges", dates), ("records", records), ("skills", []), ("ambiguous_spans", []), ("timeline_record_links", result.timeline_record_links), ("code_research_subjects", subjects))},
    }
    timeline_ids = {entry.id for entry in result.structural_audits.timeline.entries}
    return sanitize_understanding(payload, timeline_entry_ids=timeline_ids) or payload


def _sections(document, exclusion):
    headings=[]; lines=[line for page in document.pages for line in page.lines]
    for index, line in enumerate(lines):
        normalized=normalize_text(line.text.strip().rstrip(":"))
        kind=next((kind for kind, aliases in SECTION_ALIASES.items() if normalized in aliases), None)
        if kind is None or exclusion.intersects(line.page_id,line.start_offset,line.end_offset): continue
        headings.append((index,line,kind))
    result=[]
    for position,(index,line,kind) in enumerate(headings):
        end_index=(headings[position+1][0]-1) if position+1<len(headings) else len(lines)-1
        end_line=lines[max(index,end_index)]
        ev=_line_evidence(document,line)
        result.append(SectionSpan(stable_source_id(f"section-{kind.value}",line.page_id,line.start_offset,line.end_offset),kind,Confidence.HIGH,line.text.strip(),line.line_id,end_line.line_id,(ev,),index))
    return tuple(result)


def _dates(structural):
    result=[]
    for order,entry in enumerate(structural.timeline.entries):
        loc=entry.source_location
        ev=UnderstandingEvidence(loc.page_id,loc.page_number,loc.line_id,loc.start_offset,loc.end_offset,loc.association.value,entry.evidence[0].excerpt if entry.evidence else None)
        result.append(DateRangeAnnotation(stable_source_id("date-range",loc.page_id,loc.start_offset or 0,loc.end_offset or 0),entry.evidence[0].excerpt if entry.evidence else "",entry.start_month,entry.end_month,entry.start_precision,entry.end_precision,entry.status,structural.snapshot_month or "",(ev,),order))
    return tuple(result)


def _records(document, sections, dates, exclusion):
    lines={line.line_id: line for page in document.pages for line in page.lines}; ordered=list(lines.values()); positions={line.line_id:i for i,line in enumerate(ordered)}; records=[]
    for section in sections:
        if section.kind not in {SectionKind.EDUCATION,SectionKind.EMPLOYMENT}: continue
        start=positions[section.start_line_id]+1; end=positions[section.end_line_id]+1; content=[line for line in ordered[start:end] if line.text.strip()]
        groups=[]; current=[]
        for line in content:
            line_dates=[d for d in dates if d.evidence and d.evidence[0].line_id==line.line_id]
            if line_dates and current: groups.append(current); current=[]
            current.append(line)
        if current: groups.append(current)
        for group in groups:
            if any(exclusion.intersects(line.page_id,line.start_offset,line.end_offset) for line in group): continue
            record=_record_from_group(document,section,group,dates,len(records))
            if record is not None: records.append(record)
    return tuple(records)


def _record_from_group(document, section, group, dates, order):
    values=[line.text.strip() for line in group]; normalized=[normalize_text(v) for v in values]; date_ids=tuple(d.id for d in dates if d.evidence and d.evidence[0].line_id in {line.line_id for line in group})[:4]
    if section.kind is SectionKind.EDUCATION:
        identity=next((i for i,v in enumerate(normalized) if any(m in v for m in _INSTITUTION_MARKERS)),None); secondary=next((i for i,v in enumerate(normalized) if any(m in v for m in _DEGREE_MARKERS)),None)
        if identity is None or (secondary is None and not date_ids): return None
        pairs=[("institution",identity),("degree",secondary),("study_dates",next((i for i,line in enumerate(group) if any(d.evidence[0].line_id==line.line_id for d in dates if d.evidence)),None))]; kind="education"
    else:
        relation=next((i for i,v in enumerate(normalized) if v in _RELATIONSHIPS),None); role=next((i for i,v in enumerate(normalized) if any(m in v for m in _ROLE_MARKERS)),None); identity=next((i for i in range(len(values)) if i!=role and i!=relation and not any(d.evidence[0].line_id==group[i].line_id for d in dates if d.evidence)),None)
        if identity is None and relation is None: return None
        if role is None and not date_ids: return None
        pairs=[("organization",identity),("role",role),("relationship_type",relation),("employment_dates",next((i for i,line in enumerate(group) if any(d.evidence[0].line_id==line.line_id for d in dates if d.evidence)),None))]; kind="employment"
    fields=[]
    for name,index in pairs:
        if index is None: fields.append(StructuredField(name,"unknown",None,Confidence.LOW,()))
        else: fields.append(StructuredField(name,"supported",values[index][:256],Confidence.HIGH,(_line_evidence(document,group[index]),)))
    first=group[0]; last=group[-1]
    return StructuredRecord(stable_source_id(f"record-{kind}",first.page_id,first.start_offset,last.end_offset),kind,section.id,Confidence.HIGH,tuple(fields),date_ids,order)


def _subjects(records):
    result=[]; seen=set()
    for record in records:
        name="institution" if record.kind=="education" else "organization"; category="education" if record.kind=="education" else "company"
        field=next((f for f in record.fields if f.name==name and f.status=="supported" and f.value),None)
        if field is None or normalize_text(field.value) in _RELATIONSHIPS: continue
        key=subject_key(category,field.value)
        if key in seen: continue
        seen.add(key); result.append(ResearchSubject(stable_source_id(f"research-{category}",field.evidence[0].page_id,field.evidence[0].start_offset or 0,field.evidence[0].end_offset or 0),category,field.value,record.id,name,record.source_order))
    return tuple(result[:50])


def _timeline_links(records, dates, structural):
    by_literal={d.source_literal: d.id for d in dates}; result=[]
    for entry in structural.timeline.entries:
        literal=entry.evidence[0].excerpt if entry.evidence else ""; date_id=by_literal.get(literal)
        candidates=[r for r in records if date_id in r.date_range_ids]
        if len(candidates)==1: result.append({"timeline_entry_id":entry.id,"record_id":candidates[0].id})
    return tuple(result)


def _line_evidence(document, line: SourceLine):
    page=next(page for page in document.pages if page.page_id==line.page_id)
    return UnderstandingEvidence(line.page_id,page.page_number,line.line_id,line.start_offset,line.end_offset,"exact",line.text[:256])
