from __future__ import annotations

from collections import Counter
from copy import deepcopy
import re
import unicodedata
from typing import Any, Iterator, Mapping

from jsonschema import Draft202012Validator

from cv_validator.ai.domain import ValidatedDocumentAnalysis
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    SCHEMA_VERSION,
    load_document_analysis_schema,
)
from cv_validator.ingestion import RedactedDocument, SourcePage
from cv_validator.document_understanding.relationships import is_self_employment_label


REQUIRED_CHECK_IDS = frozenset(
    {
        "contact",
        "education",
        "employment",
        "timeline",
        "duration_claims",
        "relationships",
        "document_quality",
        "protected_boundaries",
    }
)
PARTIAL_VALIDATION_WARNING = (
    "Część danych nie została pokazana, ponieważ nie udało się potwierdzić "
    "ich w tekście CV."
)
MODEL_CONCLUSION_REVIEW_WARNING = (
    "Model notes were preserved and require human review."
)
_CATEGORY_CHECK_IDS = {
    "contact_conflict": "contact",
    "missing_contact_data": "contact",
    "timeline_gap": "timeline",
    "timeline_overlap": "timeline",
    "duration_claim_conflict": "duration_claims",
    "relationship_ambiguity": "relationships",
    "document_artifact": "document_quality",
    "semantic_outlier": "employment",
    "education_outside_eu": "education",
}
_FORBIDDEN_AUTHORED_PATTERNS = (
    re.compile(
        r"\b(?:score|band|verdict|ranking|hiring recommendation|nationality|"
        r"ethnicity|race|racial|national origin|appearance|religion|health|"
        r"age|gender|sex|family status|work eligibility)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:the\s+)?(?:candidate|applicant|person)\s+"
        r"(?:is|appears|seems|may be|is likely)\s+[^.!?\n]{1,100}?\s+"
        r"based on\s+(?:their\s+|the\s+)?"
        r"(?:name|surname|photo|appearance|language|school|university)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:(?:do not|don't|should not|must not)\s+"
        r"(?:interview|hire|advance|progress|select|consider)|"
        r"(?:reject|advance|hire)\s+(?:(?:this|the)\s+)?"
        r"(?:candidate|applicant)|"
        r"recommend(?:ation)?\s+(?:to\s+)?(?:hire|reject|advance))\b",
        re.IGNORECASE,
    ),
)
_SOURCE_CORRUPTION_PATTERNS = (
    re.compile(r"\ufffd"),
    re.compile(r"\?{2,}"),
    re.compile(r"(?:\{\{|\}\}|<[^>]{1,80}>|&(?:#\d+|[A-Za-z]+);)"),
    re.compile(r"(?:\\x[0-9A-Fa-f]{2}){2,}"),
)


class DocumentAnalysisValidationError(ValueError):
    """Safe validation failure that never embeds candidate content."""


def validate_document_analysis_response(
    payload: Any,
    document: RedactedDocument,
    *,
    understanding_context: Mapping[str, Any] | None = None,
) -> ValidatedDocumentAnalysis:
    if not isinstance(document, RedactedDocument):
        raise TypeError("Document Analyzer validation requires a RedactedDocument")

    return validate_document_analysis_payload(
        payload,
        pages={page.page_id: page.text for page in document.pages},
        deterministic_observations_version=DETERMINISTIC_OBSERVATIONS_VERSION,
        understanding_context=understanding_context,
    )


def validate_document_analysis_payload(
    payload: Any,
    *,
    pages: Mapping[str, str],
    deterministic_observations_version: str,
    understanding_context: Mapping[str, Any] | None = None,
) -> ValidatedDocumentAnalysis:
    """Validate/materialize the v8 model-only response.

    A bad root or unusable finding evidence is a response failure. Model-authored
    conclusions that cross a protected boundary are preserved with a warning
    instead of discarding the paid response. Individual fact fields are different: an unsupported
    optional field is discarded while independently supported fields remain.
    The model supplies only values, line IDs, and reviewer prose; code owns
    excerpts, metadata, checklist counts, and research candidates.
    """
    if (
        deterministic_observations_version != DETERMINISTIC_OBSERVATIONS_VERSION
        or not pages
        or any(
            not isinstance(page_id, str)
            or not page_id
            or not isinstance(text, str)
            for page_id, text in pages.items()
        )
    ):
        raise DocumentAnalysisValidationError(
            "AI document analysis response failed validation: context"
        )

    validator = Draft202012Validator(load_document_analysis_schema())
    if not isinstance(payload, dict) or any(validator.iter_errors(payload)):
        raise DocumentAnalysisValidationError(
            "AI document analysis response failed validation: schema"
        )

    model_conclusion_requires_review = any(
        pattern.search(text)
        for text in _iter_model_authored_conclusions_lean(payload)
        for pattern in _FORBIDDEN_AUTHORED_PATTERNS
    )
    source_lines = _source_line_index(pages)

    # Findings are reviewer-facing claims.  An unusable finding citation
    # cannot be safely shown, so it fails closed at the response boundary.
    findings: list[dict[str, Any]] = []
    for finding in payload["findings"]:
        normalized_finding = _normalize_finding_classification(finding)
        evidence = _materialize_evidence(
            normalized_finding["evidence"],
            source_lines,
            require_support=False,
        )
        if evidence is None:
            raise DocumentAnalysisValidationError(
                "AI document analysis response failed validation: finding evidence"
            )
        item = normalized_finding
        item["evidence"] = evidence
        if (
            normalized_finding["category"] == "document_artifact"
            and not _material_document_artifact(normalized_finding, evidence)
        ):
            continue
        _add_code_owned_metadata(item)
        findings.append(item)

    materialized_facts: dict[str, list[dict[str, Any]]] = {
        "contact": [],
        "education": [],
        "employment": [],
    }
    partial = False
    rejected_values: set[str] = set()
    generated_unknowns = deepcopy(payload["unknowns"])

    for contact in payload["facts"]["contact"]:
        evidence = _materialize_evidence(
            contact["evidence"],
            source_lines,
            require_support=True,
            value=contact["value"],
        )
        if evidence is None:
            # Contact has one required value, so an invalid item cannot be
            # retained as a partially supported fact.
            partial = True
            rejected_values.add(contact["value"])
            continue
        item = deepcopy(contact)
        item["evidence"] = evidence
        _add_code_owned_metadata(item)
        materialized_facts["contact"].append(item)

    composite_contracts = (
        (
            "education",
            ("institution", "program", "study_dates"),
            ("institution",),
        ),
        (
            "employment",
            (
                "organization",
                "role",
                "employment_dates",
                "location",
                "relationship_type",
            ),
            ("organization", "role"),
        ),
    )
    for kind, fields, required_fields in composite_contracts:
        for fact in payload["facts"][kind]:
            item, item_partial, item_unknowns, item_rejected_values = (
                _materialize_composite_fact(
                    fact,
                    source_lines,
                    fields=fields,
                    required_fields=required_fields,
                    field_evidence_key="field_evidence",
                    kind=kind,
                )
            )
            partial = partial or item_partial
            rejected_values.update(item_rejected_values)
            generated_unknowns.extend(item_unknowns)
            if item is not None:
                materialized_facts[kind].append(item)

    materialized_facts = {
        group: _dedupe_facts(items)
        for group, items in materialized_facts.items()
    }
    findings.extend(
        _synthesize_identity_conflicts(
            materialized_facts, understanding_context, findings
        )
    )
    for finding in findings:
        finding["check_id"] = _check_id_for_finding(finding)
    accepted_education_line_ids = {
        evidence["line_id"]
        for education in materialized_facts["education"]
        for evidence in education.get("field_evidence", {}).get("institution", [])
    }
    supported_findings = [
        finding
        for finding in findings
        if finding.get("category") != "education_outside_eu"
        or any(
            evidence.get("line_id") in accepted_education_line_ids
            for evidence in finding.get("evidence", [])
        )
    ]
    partial = partial or supported_findings != findings
    findings = supported_findings
    if rejected_values:
        # Fact fields have already been validated independently above.  Do
        # not scrub accepted facts by literal value: a supported value may be
        # shared by another fact whose citation was rejected.
        filtered_facts = materialized_facts
        filtered_findings = [
            finding
            for finding in findings
            if not _finding_mentions_unsupported_rejected_text(
                finding, rejected_values
            )
        ]
        filtered_unknowns = [
            unknown
            for unknown in generated_unknowns
            if not _contains_rejected_text(unknown, rejected_values)
        ]
        filtered_limitations = [
            limitation
            for limitation in payload["analysis_limitations"]
            if not _contains_rejected_text(limitation, rejected_values)
        ]
        partial = partial or (
            filtered_facts != materialized_facts
            or filtered_findings != findings
            or filtered_unknowns != generated_unknowns
            or filtered_limitations != payload["analysis_limitations"]
        )
        materialized_facts = filtered_facts
        findings = filtered_findings
        generated_unknowns = filtered_unknowns
        analysis_limitations = filtered_limitations
    else:
        analysis_limitations = deepcopy(payload["analysis_limitations"])
    findings = _dedupe_findings(findings)
    research_candidates = _derive_research_candidates(materialized_facts)
    checklist = _build_checklist(findings)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "facts": materialized_facts,
        "findings": findings,
        "unknowns": _dedupe_unknowns(generated_unknowns),
        "research_candidates": research_candidates,
        "checklist": checklist,
        "analysis_limitations": analysis_limitations,
    }
    validation_warnings: list[str] = []
    if partial:
        validation_warnings.append(PARTIAL_VALIDATION_WARNING)
    if model_conclusion_requires_review:
        validation_warnings.append(MODEL_CONCLUSION_REVIEW_WARNING)
    if validation_warnings:
        # This is code-owned presentation metadata; it is intentionally not
        # accepted from the model schema.
        result["validation_warnings"] = validation_warnings
    return ValidatedDocumentAnalysis(schema_version=SCHEMA_VERSION, payload=result)


def _material_document_artifact(
    finding: Mapping[str, Any],
    evidence: list[dict[str, str]],
) -> bool:
    if finding.get("material_effect") not in {
        "important_fact_unreadable",
        "meaning_changed",
    }:
        return False
    if finding.get("affected_fact") not in {
        "candidate_name",
        "phone",
        "stated_location",
        "education",
        "employment",
        "employment_dates",
        "timeline",
        "relationship",
        "document_meaning",
        "other_material_fact",
    }:
        return False
    source_text = "\n".join(
        item["excerpt"] for item in evidence
    )
    return any(
        pattern.search(source_text)
        for pattern in _SOURCE_CORRUPTION_PATTERNS
    )


def _normalize_finding_classification(finding: Mapping[str, Any]) -> dict[str, Any]:
    item = deepcopy(dict(finding))
    if item.get("category") == "document_artifact":
        if (
            item.get("material_effect") not in {"important_fact_unreadable", "meaning_changed"}
            or item.get("affected_fact") == "not_applicable"
        ):
            raise DocumentAnalysisValidationError(
                "AI document analysis response failed validation: finding classification"
            )
        return item
    item["material_effect"] = "none"
    if item.get("category") != "internal_fact_conflict" or item.get("affected_fact") not in {
        "candidate_name", "phone", "stated_location", "education", "employment",
        "employment_dates", "relationship",
    }:
        item["affected_fact"] = "not_applicable"
    return item


def _materialize_evidence(
    evidence: Any,
    source_lines: Mapping[str, tuple[str, str]],
    *,
    require_support: bool,
    value: str | None = None,
) -> list[dict[str, str]] | None:
    """Resolve line references and optionally prove one field value.

    Duplicate line references are a model formatting issue, not a reason to
    discard otherwise valid evidence.  They are removed while preserving the
    first occurrence.  Unknown or cross-page references remain fail-closed.
    """
    if not isinstance(evidence, list):
        return None
    materialized: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in evidence:
        if not isinstance(entry, dict):
            return None
        page_id = entry.get("page_id")
        line_id = entry.get("line_id")
        if (
            not isinstance(page_id, str)
            or not isinstance(line_id, str)
            or line_id in seen
            or line_id not in source_lines
            or source_lines[line_id][0] != page_id
            or not source_lines[line_id][1]
            or "█" in source_lines[line_id][1]
        ):
            if line_id in seen:
                continue
            return None
        seen.add(line_id)
        materialized.append(
            {
                "page_id": page_id,
                "line_id": line_id,
                "excerpt": source_lines[line_id][1],
            }
        )
    if not materialized:
        return None
    if require_support and (
        not isinstance(value, str)
        or not _value_is_supported(value, materialized, source_lines)
    ):
        return None
    return materialized


def _value_is_supported(
    value: str,
    evidence: list[dict[str, str]],
    source_lines: Mapping[str, tuple[str, str]],
) -> bool:
    normalized = _normalize_literal(value)
    if not normalized:
        return False
    lines = [
        (
            item["line_id"],
            item["page_id"],
            int(item["line_id"].rsplit("-line-", 1)[1]),
            source_lines[item["line_id"]][1],
        )
        for item in evidence
    ]
    if any(normalized in _normalize_literal(line) for *_, line in lines):
        return True
    return _semantic_value_is_supported_by_local_window(value, lines)


def _materialize_composite_fact(
    fact: dict[str, Any],
    source_lines: Mapping[str, tuple[str, str]],
    *,
    fields: tuple[str, ...],
    required_fields: tuple[str, ...],
    field_evidence_key: str,
    kind: str,
) -> tuple[dict[str, Any] | None, bool, list[dict[str, str]], set[str]]:
    item = deepcopy(fact)
    field_evidence: dict[str, list[dict[str, str]]] = {}
    partial = False
    unknowns: list[dict[str, str]] = []
    rejected_values: set[str] = set()
    for field in fields:
        field_value = item.get(field)
        if not isinstance(field_value, dict):
            return None, True, unknowns, rejected_values
        value = field_value.get("value")
        refs = _line_ids_to_evidence(field_value.get("line_ids"), source_lines)
        if value is None and refs == []:
            if field in required_fields:
                return None, True, unknowns, rejected_values
            item[field] = None
            field_evidence[field] = []
            continue
        materialized = _materialize_evidence(
            refs,
            source_lines,
            require_support=True,
            value=value,
        )
        if materialized is None:
            if isinstance(value, str) and value.strip():
                rejected_values.add(value)
            if field in required_fields:
                # The remaining fields cannot safely be represented as this
                # composite entry without its identity-bearing value.
                return None, True, unknowns, rejected_values
            item[field] = None
            field_evidence[field] = []
            partial = True
            unknowns.append(
                {
                    "field": _unknown_field_name(kind, field),
                    "reason": "The CV text does not support this field.",
                }
            )
            continue
        item[field] = value
        field_evidence[field] = materialized
    item[field_evidence_key] = field_evidence
    _add_code_owned_metadata(item)
    return item, partial, unknowns, rejected_values


def _line_ids_to_evidence(
    line_ids: Any,
    source_lines: Mapping[str, tuple[str, str]],
) -> list[dict[str, str]] | None:
    if not isinstance(line_ids, list):
        return None
    evidence: list[dict[str, str]] = []
    for line_id in line_ids:
        if not isinstance(line_id, str) or line_id not in source_lines:
            return None
        if "█" in source_lines[line_id][1]:
            return None
        evidence.append(
            {"page_id": source_lines[line_id][0], "line_id": line_id}
        )
    return evidence


def _unknown_field_name(kind: str, field: str) -> str:
    if kind == "education":
        return {
            "institution": "education_institution",
            "program": "education_program",
            "study_dates": "education_dates",
        }[field]
    return {
        "organization": "employment_organization",
        "role": "employment_role",
        "employment_dates": "employment_dates",
        "location": "employment_location",
        "relationship_type": "relationship_type",
    }[field]


def _contains_rejected_text(value: Any, rejected_values: set[str]) -> bool:
    if isinstance(value, str):
        normalized = _normalize_literal(value)
        return any(
            normalized_value
            and re.search(
                rf"(?<!\w){re.escape(normalized_value)}(?!\w)",
                normalized,
            )
            for normalized_value in (
                _normalize_literal(rejected) for rejected in rejected_values
            )
        )
    if isinstance(value, dict):
        return any(
            _contains_rejected_text(child, rejected_values)
            for child in value.values()
        )
    if isinstance(value, list):
        return any(
            _contains_rejected_text(child, rejected_values) for child in value
        )
    return False


def _finding_mentions_unsupported_rejected_text(
    finding: Mapping[str, Any],
    rejected_values: set[str],
) -> bool:
    evidence_text = " ".join(
        evidence.get("excerpt", "")
        for evidence in finding.get("evidence", [])
        if isinstance(evidence, dict) and isinstance(evidence.get("excerpt"), str)
    )
    if not evidence_text:
        return any(
            _contains_rejected_text(finding.get(field), rejected_values)
            for field in ("observation", "reason", "limitation")
        )
    return any(
        _contains_rejected_text(finding.get(field), rejected_values)
        and not _contains_rejected_text(evidence_text, rejected_values)
        for field in ("observation", "reason", "limitation")
    )


def value_is_supported_by_source(
    value: str,
    evidence: list[dict[str, Any]],
    pages: Mapping[str, str],
) -> bool:
    """Expose the runtime field-support predicate to the offline evaluator."""
    source_lines = _source_line_index(pages)
    return _value_is_supported(value, evidence, source_lines)


def _add_code_owned_metadata(item: dict[str, Any]) -> None:
    # These values are deliberately assigned after schema validation.  The
    # model contract does not get to claim authority or provenance.
    item["authority"] = "ai"
    item["source"] = "document_analyzer"


def _check_id_for_finding(finding: Mapping[str, Any]) -> str:
    category = finding.get("category")
    if category == "internal_fact_conflict":
        return {
            "candidate_name": "contact", "phone": "contact",
            "stated_location": "contact", "education": "education",
            "employment": "employment", "employment_dates": "employment",
            "relationship": "employment",
        }.get(finding.get("affected_fact"), "document_quality")
    return _CATEGORY_CHECK_IDS.get(str(category), "document_quality")


def _synthesize_identity_conflicts(
    facts: Mapping[str, list[dict[str, Any]]],
    understanding: Mapping[str, Any] | None,
    existing_findings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(understanding, Mapping):
        return []
    conflicts: list[dict[str, Any]] = []
    identity_fields = {"education": "institution", "employment": "organization"}
    for record in list(understanding.get("records", []))[:100]:
        if not isinstance(record, Mapping):
            continue
        kind = record.get("kind")
        identity = identity_fields.get(kind)
        if identity is None:
            continue
        code_field = next((field for field in list(record.get("fields", []))[:8]
            if isinstance(field, Mapping) and field.get("name") == identity
            and field.get("status") == "supported" and isinstance(field.get("value"), str)), None)
        if code_field is None:
            continue
        code_lines = {item.get("line_id") for item in list(code_field.get("evidence", []))[:4]
            if isinstance(item, Mapping) and item.get("line_id")}
        for fact in facts.get(kind, []):
            ai_value = fact.get(identity)
            evidence = fact.get("field_evidence", {}).get(identity, [])
            ai_lines = {item.get("line_id") for item in evidence if isinstance(item, Mapping)}
            if not code_lines.intersection(ai_lines) or _identity_key(ai_value) == _identity_key(code_field["value"]):
                continue
            if any(
                finding.get("category") == "internal_fact_conflict"
                and finding.get("affected_fact") == kind
                and ai_lines.intersection(
                    item.get("line_id") for item in finding.get("evidence", [])
                    if isinstance(item, Mapping)
                )
                for finding in existing_findings
            ):
                continue
            conflicts.append({
                "category": "internal_fact_conflict", "status": "conflicting",
                "observation": f"AI and code read different {kind} identities from the same source.",
                "reason": "The code-owned identity remains authoritative; the AI reading is retained for human review.",
                "importance": "attention", "confidence": "medium",
                "limitation": "The document alone does not resolve the competing interpretations.",
                "material_effect": "none", "affected_fact": kind,
                "evidence": deepcopy(evidence), "authority": "code", "source": "reconciliation",
            })
    return conflicts


def _identity_key(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _build_checklist(findings: list[dict[str, Any]]) -> dict[str, dict[str, int | bool]]:
    counts = Counter(finding["check_id"] for finding in findings)
    return {
        check_id: {"checked": True, "issue_count": counts[check_id]}
        for check_id in sorted(REQUIRED_CHECK_IDS)
    }


def _derive_research_candidates(
    facts: Mapping[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Build optional research inputs only from accepted, evidenced facts."""
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(category: str, subject: Any, evidence: list[dict[str, Any]], question: str) -> None:
        if not isinstance(subject, str) or not subject.strip() or not evidence:
            return
        key = (category, subject.strip().casefold())
        if key in seen:
            return
        seen.add(key)
        candidates.append(
            {
                "category": category,
                "query_subject": subject.strip(),
                "question": question,
                "authority": "ai",
                "source": "document_analyzer",
                # Research services accept one source anchor.  The accepted
                # fact remains the authority for the candidate itself.
                "evidence": deepcopy(evidence[0]),
            }
        )

    for contact in facts.get("contact", []):
        if contact.get("kind") == "candidate_name":
            add(
                "linkedin",
                contact.get("value"),
                contact.get("evidence", []),
                "Look for possible public professional profiles; do not claim identity.",
            )
    for education in facts.get("education", []):
        evidence = education.get("field_evidence", {})
        add(
            "education_or_certification",
            education.get("institution"),
            evidence.get("institution", []),
            "Check the public institution and credential details.",
        )
        add(
            "education_or_certification",
            education.get("program"),
            evidence.get("program", []),
            "Check the public program or credential details.",
        )
    for employment in facts.get("employment", []):
        evidence = employment.get("field_evidence", {})
        organization = employment.get("organization")
        if _is_named_organization(organization):
            add(
                "company",
                organization,
                evidence.get("organization", []),
                "Check the public organization details without inferring a person relationship.",
            )
    return candidates


def _is_named_organization(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and not is_self_employment_label(value)


def _dedupe_facts(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = tuple(
            item.get(field)
            for field in (
                "kind",
                "value",
                "institution",
                "program",
                "study_dates",
                "organization",
                "role",
                "employment_dates",
                "location",
                "relationship_type",
            )
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = item
            result.append(item)
            continue
        _merge_evidence(existing, item)
    return result


def _merge_evidence(target: dict[str, Any], source: dict[str, Any]) -> None:
    if isinstance(target.get("evidence"), list) and isinstance(
        source.get("evidence"), list
    ):
        target["evidence"] = _dedupe_evidence(
            [*target["evidence"], *source["evidence"]]
        )
    for field in ("field_evidence",):
        target_fields = target.get(field)
        source_fields = source.get(field)
        if not isinstance(target_fields, dict) or not isinstance(source_fields, dict):
            continue
        for name, source_evidence in source_fields.items():
            if not isinstance(source_evidence, list):
                continue
            target_fields[name] = _dedupe_evidence(
                [*(target_fields.get(name) or []), *source_evidence]
            )


def _dedupe_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in evidence:
        if not isinstance(item, dict):
            continue
        key = (item.get("page_id"), item.get("line_id"))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _dedupe_findings(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for item in items:
        key = tuple(
            item.get(field)
            for field in ("category", "status", "observation", "reason")
        )
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = item
            result.append(item)
        else:
            _merge_evidence(existing, item)
    return result


def _dedupe_unknowns(unknowns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for unknown in unknowns:
        if not isinstance(unknown, dict):
            continue
        key = (unknown.get("field"), unknown.get("reason"))
        if key in seen:
            continue
        seen.add(key)
        result.append(unknown)
    return result


def _iter_model_authored_conclusions_lean(payload: dict[str, Any]) -> Iterator[str]:
    for finding in payload["findings"]:
        yield finding["observation"]
        yield finding["reason"]
        yield finding["limitation"]
    for unknown in payload["unknowns"]:
        yield unknown["reason"]
    yield from payload["analysis_limitations"]


def _source_line_index(
    pages: Mapping[str, str],
) -> dict[str, tuple[str, str]]:
    index: dict[str, tuple[str, str]] = {}
    for page_number, (page_id, text) in enumerate(pages.items(), start=1):
        page = SourcePage(page_id, page_number, text)
        for line in page.lines:
            index[line.line_id] = (page_id, line.text)
    return index


def _normalize_literal(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = normalized.translate(str.maketrans({"–": "-", "—": "-", "−": "-"}))
    return " ".join(normalized.split())


def _normalize_semantic_literal(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    without_punctuation = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return " ".join(without_punctuation.split())


def _tokens_are_subsequence(
    expected_tokens: list[str],
    source_tokens: list[str],
) -> bool:
    source = iter(source_tokens)
    return all(any(token == candidate for candidate in source) for token in expected_tokens)


def _semantic_value_is_supported_by_local_window(
    value: str,
    evidence_lines: list[tuple[str, str, int, str]],
) -> bool:
    expected_tokens = _normalize_semantic_literal(value).split()
    if not expected_tokens:
        return False
    lines_by_page: dict[str, list[tuple[int, str]]] = {}
    for _, page_id, line_number, text in evidence_lines:
        lines_by_page.setdefault(page_id, []).append((line_number, text))
    for page_lines in lines_by_page.values():
        ordered_lines = sorted(page_lines)
        for start in range(len(ordered_lines)):
            for end in range(start + 2, min(start + 3, len(ordered_lines)) + 1):
                window = ordered_lines[start:end]
                if window[-1][0] - window[0][0] > 4:
                    continue
                if any(
                    later[0] - earlier[0] > 2
                    for earlier, later in zip(window, window[1:])
                ):
                    continue
                source_tokens = _normalize_semantic_literal(
                    " ".join(text for _, text in window)
                ).split()
                if _tokens_are_subsequence(expected_tokens, source_tokens):
                    return True
    return False
