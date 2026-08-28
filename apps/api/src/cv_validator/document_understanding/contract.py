from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

CONTRACT_VERSION = "document-understanding-v1"
LIMITS = {"sections": 32, "date_ranges": 100, "records": 100, "skills": 200, "ambiguous_spans": 100, "timeline_record_links": 100, "code_research_subjects": 50}
TOP_KEYS = {"contract_version", "status", "parser_version", "ruleset_version", "snapshot_month", "coverage", *LIMITS, "truncation"}
ENUMS = {
    "status": {"completed", "partial", "unavailable", "not_applicable"},
    "kind.section": {"contact", "summary", "employment", "education", "skills", "certifications", "projects", "languages", "publications", "awards", "volunteering", "references", "other"},
    "kind.record": {"education", "employment"}, "confidence": {"high", "medium", "low"},
    "association": {"exact", "partial"}, "field_status": {"supported", "unknown", "ambiguous"},
    "date_status": {"valid", "invalid", "unresolved"}, "precision": {"month", "year", "open_ended", "unknown"},
    "research_category": {"company", "education"}, "ambiguous_category": {"section", "date", "entry", "field", "skill"},
}
AUDITED = {"canonical_pages", "source_blocks", "presentation_spans", "section_annotations", "date_annotations", "entry_annotations", "skill_taxonomy"}
OMITTED = {"docx_headers", "docx_footers", "docx_textboxes", "docx_footnotes_endnotes", "docx_comments", "docx_drawings", "docx_embedded_files", "pdf_images_ocr", "pdf_non_text_content", "source_blocks_unavailable", "presentation_spans_unavailable", "sections_truncated", "date_ranges_truncated", "records_truncated", "skills_unavailable", "skills_truncated", "ambiguous_spans_truncated", "timeline_record_links_truncated", "code_research_subjects_truncated"}
FIELD_NAMES = {"institution", "program", "degree", "study_dates", "result", "education_location", "organization", "role", "relationship_type", "employment_dates", "employment_location"}
EDUCATION_FIELDS = {"institution", "program", "degree", "study_dates", "result", "education_location"}
EMPLOYMENT_FIELDS = {"organization", "role", "relationship_type", "employment_dates", "employment_location"}
_MONTH = re.compile(r"^\d{4}-(?:0[1-9]|1[0-2])$")


class UnderstandingContractError(ValueError):
    pass


def sanitize_understanding(value: Any, *, timeline_entry_ids: set[str] | None = None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = deepcopy(value)
    _object(payload, TOP_KEYS, "understanding")
    _eq(payload["contract_version"], CONTRACT_VERSION, "contract_version")
    _enum(payload["status"], ENUMS["status"], "status")
    _short(payload["parser_version"], 128, "parser_version"); _short(payload["ruleset_version"], 128, "ruleset_version")
    _month(payload["snapshot_month"], "snapshot_month")
    _coverage(payload["coverage"])
    for name in LIMITS:
        if not isinstance(payload[name], list): raise UnderstandingContractError(f"{name} must be an array")
    _truncate(payload)
    sections = {_section(x)["id"] for x in payload["sections"]}
    dates = {_date(x, payload["snapshot_month"])["id"] for x in payload["date_ranges"]}
    records: dict[str, dict[str, Any]] = {}
    for item in payload["records"]:
        record = _record(item, sections, dates); records[record["id"]] = record
    for item in payload["skills"]: _skill(item)
    for item in payload["ambiguous_spans"]: _ambiguous(item)
    for item in payload["timeline_record_links"]:
        _object(item, {"timeline_entry_id", "record_id"}, "timeline link"); _short(item["timeline_entry_id"], 128, "timeline_entry_id"); _short(item["record_id"], 128, "record_id")
        if item["record_id"] not in records or (timeline_entry_ids is not None and item["timeline_entry_id"] not in timeline_entry_ids): raise UnderstandingContractError("unresolved timeline link")
    for item in payload["code_research_subjects"]: _subject(item, records)
    _truncation(payload["truncation"])
    _unique_ids(payload)
    if _contains_forbidden_identifier(payload): raise UnderstandingContractError("forbidden sensitive identifier")
    return payload


def _truncate(p: dict[str, Any]) -> None:
    omitted = list(p["coverage"]["omitted_parts"]); changed = False
    for name, limit in LIMITS.items():
        values = p[name]; total = len(values); p[name] = values[:limit]
        if total > limit:
            changed = True; code = f"{name}_truncated"; omitted.append(code) if code not in omitted else None
    section_ids = {x.get("id") for x in p["sections"]}; date_ids = {x.get("id") for x in p["date_ranges"]}
    before = len(p["records"]); p["records"] = [x for x in p["records"] if x.get("section_id") in section_ids and set(x.get("date_range_ids", [])) <= date_ids]
    if len(p["records"]) < before: changed = True; omitted.append("records_truncated") if "records_truncated" not in omitted else None
    record_ids = {x.get("id") for x in p["records"]}
    for name in ("timeline_record_links", "code_research_subjects"):
        before = len(p[name]); p[name] = [x for x in p[name] if x.get("record_id") in record_ids]
        if len(p[name]) < before: changed = True; code=f"{name}_truncated"; omitted.append(code) if code not in omitted else None
    p["coverage"]["omitted_parts"] = omitted
    if changed: p["status"] = p["coverage"]["status"] = "partial"
    for name in LIMITS:
        original = p["truncation"].get(name, {}); additional = max(0, original.get("reported_count", len(p[name])) + original.get("additional_count", 0) - len(p[name]))
        p["truncation"][name] = {"reported_count": len(p[name]), "additional_count": additional, "truncated": additional > 0}


def _evidence(x: Any) -> None:
    _object(x, {"page_id", "page_number", "line_id", "start_offset", "end_offset", "association", "excerpt"}, "evidence")
    _short(x["page_id"], 128, "page_id"); _integer(x["page_number"], 1, "page_number"); _nullable_short(x["line_id"], 128, "line_id"); _enum(x["association"], ENUMS["association"], "association")
    if x["association"] == "exact":
        _integer(x["start_offset"], 0, "start_offset"); _integer(x["end_offset"], 1, "end_offset")
        if x["start_offset"] >= x["end_offset"]: raise UnderstandingContractError("invalid exact evidence offsets")
    elif (x["start_offset"] is None) != (x["end_offset"] is None): raise UnderstandingContractError("partial offsets must be paired")
    _nullable_short(x["excerpt"], 256, "excerpt")


def _evidence_list(values: Any) -> None:
    if not isinstance(values, list) or len(values) > 4: raise UnderstandingContractError("evidence must be a bounded array")
    for x in values: _evidence(x)


def _coverage(x: Any) -> None:
    _object(x, {"status", "source_format", "audited_parts", "omitted_parts"}, "coverage"); _enum(x["status"], ENUMS["status"], "coverage status"); _enum(x["source_format"], {"pdf", "docx", "text"}, "source_format")
    _unique_enum_list(x["audited_parts"], AUDITED, 16, "audited_parts"); _unique_enum_list(x["omitted_parts"], OMITTED, 32, "omitted_parts")


def _section(x: Any) -> dict[str, Any]:
    _object(x, {"id", "kind", "confidence", "heading", "start_line_id", "end_line_id", "evidence"}, "section"); _short(x["id"],128,"section id"); _enum(x["kind"],ENUMS["kind.section"],"section kind"); _enum(x["confidence"],ENUMS["confidence"],"confidence"); _short(x["heading"],128,"heading"); _short(x["start_line_id"],128,"start_line_id"); _short(x["end_line_id"],128,"end_line_id"); _evidence_list(x["evidence"]); return x


def _date(x: Any, snapshot: str) -> dict[str, Any]:
    _object(x,{"id","source_literal","start_month","end_month","start_precision","end_precision","status","snapshot_month","evidence"},"date range"); _short(x["id"],128,"date id"); _short(x["source_literal"],128,"source_literal"); _nullable_month(x["start_month"],"start_month"); _nullable_month(x["end_month"],"end_month"); _enum(x["start_precision"],ENUMS["precision"],"precision"); _enum(x["end_precision"],ENUMS["precision"],"precision"); _enum(x["status"],ENUMS["date_status"],"date status"); _eq(x["snapshot_month"],snapshot,"date snapshot"); _evidence_list(x["evidence"]); return x


def _record(x: Any, sections: set[str], dates: set[str]) -> dict[str, Any]:
    _object(x,{"id","kind","section_id","confidence","fields","date_range_ids"},"record"); _short(x["id"],128,"record id"); _enum(x["kind"],ENUMS["kind.record"],"record kind"); _short(x["section_id"],128,"section_id"); _enum(x["confidence"],ENUMS["confidence"],"confidence")
    if x["section_id"] not in sections: raise UnderstandingContractError("unresolved record section")
    if not isinstance(x["date_range_ids"],list) or len(x["date_range_ids"])>4 or len(x["date_range_ids"])!=len(set(x["date_range_ids"])) or not set(x["date_range_ids"])<=dates: raise UnderstandingContractError("invalid record date references")
    if not isinstance(x["fields"],list) or len(x["fields"])>8: raise UnderstandingContractError("invalid record fields")
    allowed = EDUCATION_FIELDS if x["kind"]=="education" else EMPLOYMENT_FIELDS; names=[]
    for field in x["fields"]: names.append(_field(field,allowed))
    if len(names)!=len(set(names)): raise UnderstandingContractError("duplicate record field")
    return x


def _field(x: Any, allowed: set[str]) -> str:
    _object(x,{"name","status","value","authority","confidence","evidence"},"field"); _enum(x["name"],allowed,"field name"); _enum(x["status"],ENUMS["field_status"],"field status"); _eq(x["authority"],"code","field authority"); _enum(x["confidence"],ENUMS["confidence"],"confidence"); _nullable_short(x["value"],256,"field value"); _evidence_list(x["evidence"])
    if x["status"]=="supported" and (x["value"] is None or not x["evidence"]): raise UnderstandingContractError("supported field requires value and evidence")
    if x["status"]=="unknown" and (x["value"] is not None or x["evidence"]): raise UnderstandingContractError("unknown field must be empty")
    if x["status"]=="ambiguous" and not x["evidence"]: raise UnderstandingContractError("ambiguous field requires evidence")
    return x["name"]


def _skill(x: Any)->None:
    _object(x,{"id","canonical_id","display_label","taxonomy","taxonomy_version","confidence","evidence"},"skill"); _short(x["id"],128,"skill id"); _short(x["canonical_id"],128,"canonical_id"); _short(x["display_label"],128,"display_label"); _eq(x["taxonomy"],"esco","taxonomy"); _short(x["taxonomy_version"],128,"taxonomy_version"); _enum(x["confidence"],ENUMS["confidence"],"confidence"); _evidence_list(x["evidence"])


def _ambiguous(x: Any)->None:
    _object(x,{"id","category","reason_code","evidence"},"ambiguous span"); _short(x["id"],128,"ambiguous id"); _enum(x["category"],ENUMS["ambiguous_category"],"ambiguous category"); _short(x["reason_code"],128,"reason_code"); _evidence_list(x["evidence"])


def _subject(x:Any, records:dict[str,dict[str,Any]])->None:
    _object(x,{"id","category","subject","record_id","field_name"},"research subject"); _short(x["id"],128,"subject id"); _enum(x["category"],ENUMS["research_category"],"research category"); _short(x["subject"],256,"subject"); _short(x["record_id"],128,"record_id"); _enum(x["field_name"],{"institution","organization"},"subject field")
    record=records.get(x["record_id"]); expected="education" if x["field_name"]=="institution" else "employment"
    if record is None or record["kind"]!=expected or not any(f["name"]==x["field_name"] and f["status"]=="supported" and f["value"]==x["subject"] for f in record["fields"]): raise UnderstandingContractError("research subject lacks supported identity field")


def _truncation(x:Any)->None:
    _object(x,set(LIMITS),"truncation")
    for item in x.values(): _object(item,{"reported_count","additional_count","truncated"},"truncation record"); _integer(item["reported_count"],0,"reported_count"); _integer(item["additional_count"],0,"additional_count");


def _unique_ids(p:dict[str,Any])->None:
    ids=[]
    for name in ("sections","date_ranges","records","skills","ambiguous_spans","code_research_subjects"): ids.extend(x["id"] for x in p[name])
    if len(ids)!=len(set(ids)): raise UnderstandingContractError("duplicate understanding id")


def _contains_forbidden_identifier(value: Any) -> bool:
    from cv_validator.ingestion.redaction import _find_sensitive_spans
    if isinstance(value, str):
        return bool(_find_sensitive_spans(value))
    if isinstance(value, dict):
        return any(_contains_forbidden_identifier(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_forbidden_identifier(item) for item in value)
    return False


def _object(x:Any, keys:set[str], label:str)->None:
    if not isinstance(x,dict) or set(x)!=keys: raise UnderstandingContractError(f"{label} has unknown or missing fields")
def _enum(x:Any, allowed:set[str], label:str)->None:
    if not isinstance(x,str) or x not in allowed: raise UnderstandingContractError(f"invalid {label}")
def _eq(x:Any, expected:Any,label:str)->None:
    if x!=expected: raise UnderstandingContractError(f"invalid {label}")
def _short(x:Any,n:int,label:str)->None:
    if not isinstance(x,str) or not x or len(x)>n: raise UnderstandingContractError(f"invalid {label}")
def _nullable_short(x:Any,n:int,label:str)->None:
    if x is not None: _short(x,n,label)
def _integer(x:Any,minimum:int,label:str)->None:
    if isinstance(x,bool) or not isinstance(x,int) or x<minimum: raise UnderstandingContractError(f"invalid {label}")
def _month(x:Any,label:str)->None:
    if not isinstance(x,str) or not _MONTH.fullmatch(x): raise UnderstandingContractError(f"invalid {label}")
def _nullable_month(x:Any,label:str)->None:
    if x is not None: _month(x,label)
def _unique_enum_list(x:Any,allowed:set[str],limit:int,label:str)->None:
    if not isinstance(x,list) or len(x)>limit or len(x)!=len(set(x)) or not set(x)<=allowed: raise UnderstandingContractError(f"invalid {label}")
