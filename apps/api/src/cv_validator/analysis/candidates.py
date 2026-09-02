from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
import unicodedata

from cv_validator.analysis.source import SourceBlock, SourceDocument


PROFILE_SCALARS = ("candidate_name", "declared_location", "headline", "summary")
PROFILE_LISTS = ("skills", "languages")
EMPLOYMENT_FIELDS = (
    "organization",
    "role",
    "start_date",
    "end_date",
    "location",
    "relationship_type",
)
EDUCATION_FIELDS = (
    "institution",
    "program",
    "degree",
    "certificate",
    "start_date",
    "end_date",
    "location",
)
MAX_RECORDS = 100
MAX_LIST_FIELDS = 200
MAX_TEXT_LENGTH = 4000
REVIEW_ANNOTATION_KINDS = frozenset({
    "suspected_hallucination",
    "unsupported_evidence",
    "uncertain_relation",
    "conflicting_relation",
    "duplicate",
})


@dataclass
class CandidateState:
    profile: dict[str, Any]
    employment: list[dict[str, Any]]
    education: list[dict[str, Any]]
    rejected: list[dict[str, str]]
    conflicts: list[dict[str, Any]]

    @property
    def records(self) -> dict[str, dict[str, Any]]:
        return {item["id"]: item for item in [*self.employment, *self.education]}

    @property
    def field_ids(self) -> set[str]:
        result: set[str] = set()
        for value in self.profile.values():
            values = value if isinstance(value, list) else [value]
            result.update(item["_id"] for item in values if isinstance(item, dict))
        for record in self.records.values():
            result.update(
                field["_id"]
                for name, field in record.items()
                if name in {*EMPLOYMENT_FIELDS, *EDUCATION_FIELDS}
                and isinstance(field, dict)
            )
        return result


def validate_specialists(
    source: SourceDocument,
    profile_payload: Any,
    employment_payload: Any,
    education_payload: Any,
) -> CandidateState:
    rejected: list[dict[str, str]] = []
    conflicts: list[dict[str, Any]] = []
    profile = _validate_profile(source, profile_payload, rejected)
    employment = _validate_records(
        source,
        employment_payload,
        "employment",
        EMPLOYMENT_FIELDS,
        rejected,
        conflicts,
    )
    education = _validate_records(
        source,
        education_payload,
        "education",
        EDUCATION_FIELDS,
        rejected,
        conflicts,
    )
    _remove_duplicate_ids(employment, education, rejected)
    return CandidateState(profile, employment, education, rejected, conflicts)


def apply_review(
    source: SourceDocument,
    state: CandidateState,
    review_payload: Any,
    *,
    review_status: str | None = None,
) -> tuple[CandidateState, dict[str, Any]]:
    payload = review_payload if isinstance(review_payload, dict) else {}
    known_records = state.records
    known_fields = state.field_ids
    rejected = list(state.rejected)
    conflicts = [*state.conflicts, *_safe_objects(payload.get("conflicts"), 300)]
    coverage_gaps = _safe_objects(payload.get("coverage_gaps"), 100)

    annotations: list[dict[str, str]] = []
    annotated_ids: set[str] = set()
    for item in _safe_objects(payload.get("annotations"), 300):
        record_id = item.get("record_id")
        kind = item.get("kind")
        reason = item.get("reason_code")
        if record_id not in known_records:
            conflicts.append({"reason_code": "unknown_reviewer_record_id"})
            continue
        if kind not in REVIEW_ANNOTATION_KINDS or not isinstance(reason, str) or not reason or len(reason) > 128:
            conflicts.append({
                "record_id": record_id,
                "reason_code": "invalid_reviewer_annotation",
            })
            continue
        annotations.append({"record_id": record_id, "kind": kind, "reason_code": reason})
        annotated_ids.add(record_id)

    # Review is a delta over the validated specialist baseline. Omission is not
    # an instruction to discard a supported record.
    accepted_ids: set[str] = {
        record_id
        for record_id, record in known_records.items()
        if record.get("relation_status") == "supported"
    }

    corrections: list[dict[str, Any]] = []
    for patch in _safe_objects(payload.get("relation_patches"), 300):
        record_id = patch.get("record_id")
        field_ids = patch.get("field_ids")
        if record_id not in known_records or not isinstance(field_ids, list) or any(
            field_id not in known_fields for field_id in field_ids
        ):
            conflicts.append({"reason_code": "unknown_reviewer_patch_id"})
            continue
        target = known_records[record_id]
        allowed_fields = EMPLOYMENT_FIELDS if target in state.employment else EDUCATION_FIELDS
        original = _public_record(target, allowed_fields)
        field_index = _field_index(state)
        proposed = deepcopy(target)
        for field_id in dict.fromkeys(field_ids):
            field_name, field = field_index[field_id]
            if field_name not in allowed_fields:
                conflicts.append({"record_id": record_id, "reason_code": "invalid_reviewer_relation_patch"})
                break
            proposed[field_name] = deepcopy(field)
        else:
            relation = _relation_status(
                source,
                [proposed[name] for name in allowed_fields if proposed.get(name)],
            )
            if relation != "supported":
                conflicts.append({"record_id": record_id, "reason_code": "invalid_reviewer_relation_patch"})
                continue
            for name in allowed_fields:
                target[name] = proposed.get(name)
            target["relation_status"] = relation
            accepted_ids.add(record_id)
            corrections.append({
                "record_id": record_id,
                "field_ids": list(dict.fromkeys(field_ids)),
                "original_candidate": original,
                "effective_projection": _public_record(target, allowed_fields),
            })

    merge_groups = _known_merge_groups(payload.get("merge_groups"), known_records, conflicts)
    merge_originals = {
        tuple(group): [
            _public_record(
                known_records[record_id],
                EMPLOYMENT_FIELDS if known_records[record_id] in state.employment else EDUCATION_FIELDS,
            )
            for record_id in group
        ]
        for group in merge_groups
    }
    applied_merge_groups = _apply_merge_groups(
        source,
        state,
        merge_groups,
        accepted_ids,
        conflicts,
    )
    for group in applied_merge_groups:
        for duplicate_id in group[1:]:
            annotations.append({
                "record_id": duplicate_id,
                "kind": "duplicate",
                "reason_code": "reviewer_duplicate_projection",
            })
            annotated_ids.add(duplicate_id)
    merge_projections = [
        {
            "record_ids": group,
            "original_candidates": merge_originals[tuple(group)],
            "effective_projection": _public_record(
                known_records[group[0]],
                EMPLOYMENT_FIELDS if known_records[group[0]] in state.employment else EDUCATION_FIELDS,
            ),
        }
        for group in applied_merge_groups
    ]

    added_profile_fields: list[str] = []
    for addition in _safe_objects(payload.get("added_profile_fields"), 20):
        field_name = addition.get("field_name")
        if field_name not in {*PROFILE_SCALARS, *PROFILE_LISTS}:
            conflicts.append({"reason_code": "invalid_reviewer_profile_field"})
            continue
        validated = _validate_field(source, addition.get("field"))
        if validated is None:
            conflicts.append({"reason_code": "reviewer_added_candidate_invalid_evidence"})
            coverage_gaps.append({"target": "profile", "reason_code": "invalid_addition"})
            continue
        if field_name in PROFILE_LISTS:
            state.profile[field_name].append(validated)
        elif state.profile[field_name] is None:
            state.profile[field_name] = validated
        else:
            conflicts.append({"reason_code": "reviewer_profile_field_already_present"})
            continue
        added_profile_fields.append(field_name)

    added_candidate_ids: list[str] = []
    for addition in _safe_objects(payload.get("added_candidates"), 100):
        candidate_type = addition.get("candidate_type")
        candidate = addition.get("candidate")
        if candidate_type not in {"employment", "education"} or not isinstance(candidate, dict):
            conflicts.append({"reason_code": "invalid_reviewer_candidate_type"})
            continue
        candidate = deepcopy(candidate)
        candidate["id"] = addition.get("id") or candidate.get("id")
        fields = EMPLOYMENT_FIELDS if candidate_type == "employment" else EDUCATION_FIELDS
        additions_rejected: list[dict[str, str]] = []
        additions_conflicts: list[dict[str, Any]] = []
        records = _validate_records(
            source,
            {"records": [candidate]},
            candidate_type,
            fields,
            additions_rejected,
            additions_conflicts,
            added_by_reviewer=True,
        )
        if not records or records[0]["id"] in known_records:
            conflicts.append({"reason_code": "reviewer_added_candidate_invalid_evidence"})
            coverage_gaps.append({"target": candidate_type, "reason_code": "invalid_addition"})
            continue
        record = records[0]
        if record["relation_status"] != "supported":
            conflicts.append({"reason_code": "reviewer_added_candidate_invalid_relation"})
            coverage_gaps.append({"target": candidate_type, "reason_code": "unsafe_relation"})
            continue
        target = state.employment if candidate_type == "employment" else state.education
        target.append(record)
        known_records[record["id"]] = record
        accepted_ids.add(record["id"])
        added_candidate_ids.append(record["id"])

    for record in [*state.employment, *state.education]:
        record["status"] = (
            "accepted"
            if record["id"] in accepted_ids
            and record["id"] not in annotated_ids
            and record["relation_status"] == "supported"
            else "ambiguous"
        )

    accepted_final = [
        record["id"]
        for record in [*state.employment, *state.education]
        if record["status"] == "accepted"
    ]
    state.rejected = rejected
    state.conflicts = conflicts
    review = {
        "status": _review_status(payload, conflicts, coverage_gaps, review_status),
        "accepted_ids": accepted_final,
        "rejected": state.rejected,
        "annotations": annotations,
        "merged_ids": applied_merge_groups,
        "merge_projections": merge_projections,
        "relation_corrections": corrections,
        "added_profile_fields": list(dict.fromkeys(added_profile_fields)),
        "added_candidate_ids": added_candidate_ids,
        "conflicts": conflicts,
        "coverage_gaps": coverage_gaps,
    }
    return state, review


def public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        name: (
            [_public_field(item) for item in value]
            if isinstance(value, list)
            else _public_field(value)
        )
        for name, value in profile.items()
    }


def public_records(records: list[dict[str, Any]], field_names: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {
            "id": record["id"],
            "status": record["status"],
            "relation_status": record["relation_status"],
            "added_by_reviewer": record["added_by_reviewer"],
            **{name: _public_field(record.get(name)) for name in field_names},
        }
        for record in records
    ]


def _public_record(record: dict[str, Any], field_names: tuple[str, ...]) -> dict[str, Any]:
    return {
        "id": record["id"],
        **{name: _public_field(record.get(name)) for name in field_names},
    }


def _validate_profile(source: SourceDocument, payload: Any, rejected: list[dict[str, str]]) -> dict[str, Any]:
    source_payload = payload if isinstance(payload, dict) else {}
    if isinstance(source_payload.get("profile"), dict):
        source_payload = source_payload["profile"]
    result: dict[str, Any] = {}
    for name in PROFILE_SCALARS:
        result[name] = _validate_field(source, source_payload.get(name))
        if source_payload.get(name) is not None and result[name] is None:
            rejected.append({"id": str(name), "reason_code": "invalid_literal_evidence"})
    for name in PROFILE_LISTS:
        raw = source_payload.get(name, [])
        values = raw if isinstance(raw, list) else []
        result[name] = []
        for item in values[:MAX_LIST_FIELDS]:
            field = _validate_field(source, item)
            if field is not None:
                result[name].append(field)
            else:
                rejected.append({"id": str(name), "reason_code": "invalid_literal_evidence"})
    return result


def _validate_records(
    source: SourceDocument,
    payload: Any,
    candidate_type: str,
    field_names: tuple[str, ...],
    rejected: list[dict[str, str]],
    conflicts: list[dict[str, Any]],
    *,
    added_by_reviewer: bool = False,
) -> list[dict[str, Any]]:
    raw_records = payload.get("records", []) if isinstance(payload, dict) else []
    if not isinstance(raw_records, list):
        return []
    output: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_records[:MAX_RECORDS]):
        if not isinstance(raw, dict):
            rejected.append({"id": f"{candidate_type}-{index}", "reason_code": "invalid_schema"})
            continue
        record_id = raw.get("id")
        if not isinstance(record_id, str) or not record_id or len(record_id) > 256:
            rejected.append({"id": f"{candidate_type}-{index}", "reason_code": "invalid_record_id"})
            continue
        record: dict[str, Any] = {
            "id": record_id,
            "status": "ambiguous",
            "added_by_reviewer": added_by_reviewer,
        }
        for name in field_names:
            record[name] = _validate_field(source, raw.get(name))
            if raw.get(name) is not None and record[name] is None:
                conflicts.append({"record_id": record_id, "field": name, "reason_code": "invalid_literal_evidence"})
        required = "organization" if candidate_type == "employment" else "institution"
        if record[required] is None:
            rejected.append({"id": record_id, "reason_code": f"missing_{required}"})
            continue
        relation = _relation_status(source, [record[name] for name in field_names if record[name]])
        record["relation_status"] = relation
        if relation == "invalid":
            rejected.append({"id": record_id, "reason_code": "invalid_record_relation"})
            continue
        record["status"] = "accepted" if relation == "supported" else "ambiguous"
        output.append(record)
    return output


def _validate_field(source: SourceDocument, raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    field_id = raw.get("id")
    value = raw.get("value")
    evidence = raw.get("evidence")
    if (
        not isinstance(field_id, str)
        or not field_id
        or len(field_id) > 256
        or not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_TEXT_LENGTH
        or not isinstance(evidence, list)
        or not evidence
        or len(evidence) > 20
    ):
        return None
    blocks = source.by_id()
    final_evidence: list[dict[str, Any]] = []
    block_ids: list[str] = []
    for citation in evidence:
        if not isinstance(citation, dict):
            return None
        block_id = citation.get("block_id") or citation.get("source_id")
        excerpt = citation.get("excerpt")
        block = blocks.get(block_id)
        if block is None or not isinstance(excerpt, str) or not excerpt:
            return None
        normalized_text, start_offsets, end_offsets = _normalized_with_offsets(block.text)
        normalized_excerpt = _normalize_literal(excerpt)
        normalized_value = _normalize_literal(value)
        if not normalized_excerpt or not normalized_value:
            return None
        start_normalized = normalized_text.find(normalized_excerpt)
        if start_normalized < 0 or normalized_value not in normalized_excerpt:
            return None
        end_normalized = start_normalized + len(normalized_excerpt)
        start = start_offsets[start_normalized]
        end = end_offsets[end_normalized - 1]
        final_evidence.append(block.evidence(start, end))
        block_ids.append(block.id)
    return {
        "_id": field_id,
        "_block_ids": tuple(block_ids),
        "value": value,
        "status": "supported",
        "evidence": final_evidence,
    }


def _relation_status(source: SourceDocument, fields: list[dict[str, Any]]) -> str:
    block_map = source.by_id()
    cited = [block_map[block_id] for field in fields for block_id in field["_block_ids"]]
    unique: dict[str, SourceBlock] = {block.id: block for block in cited}
    blocks = list(unique.values())
    if len(blocks) <= 1:
        return "supported"
    table_blocks = [block for block in blocks if block.table_id]
    if len(table_blocks) == len(blocks):
        table_positions = {(block.table_id, block.row_index) for block in table_blocks}
        if len(table_positions) != 1:
            return "ambiguous"
        return "supported"
    if (
        len({block.parent_id for block in blocks}) == 1
        and blocks[0].parent_id not in {None, "body", "furniture"}
    ):
        return "supported"
    distance = max(block.order for block in blocks) - min(block.order for block in blocks)
    if distance <= 3:
        return "supported"
    return "ambiguous"


_TYPOGRAPHIC_EQUIVALENTS = str.maketrans({
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
})


def _normalize_literal(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).translate(_TYPOGRAPHIC_EQUIVALENTS).split())


def _normalized_with_offsets(value: str) -> tuple[str, list[int], list[int]]:
    output: list[str] = []
    start_offsets: list[int] = []
    end_offsets: list[int] = []
    in_whitespace = False
    index = 0
    while index < len(value):
        cluster_end = index + 1
        while cluster_end < len(value) and unicodedata.combining(value[cluster_end]):
            cluster_end += 1
        expanded = unicodedata.normalize("NFKC", value[index:cluster_end]).translate(_TYPOGRAPHIC_EQUIVALENTS)
        for normalized in expanded:
            if normalized.isspace():
                if output and not in_whitespace:
                    output.append(" ")
                    start_offsets.append(index)
                    end_offsets.append(cluster_end)
                elif output and in_whitespace:
                    end_offsets[-1] = cluster_end
                in_whitespace = True
            else:
                output.append(normalized)
                start_offsets.append(index)
                end_offsets.append(cluster_end)
                in_whitespace = False
        index = cluster_end
    if output and output[-1] == " ":
        output.pop()
        start_offsets.pop()
        end_offsets.pop()
    return "".join(output), start_offsets, end_offsets


def _public_field(field: Any) -> Any:
    if not isinstance(field, dict):
        return None
    return {key: deepcopy(field[key]) for key in ("value", "status", "evidence")}


def _remove_duplicate_ids(employment, education, rejected) -> None:
    seen: set[str] = set()
    for collection in (employment, education):
        retained = []
        for record in collection:
            if record["id"] in seen:
                rejected.append({"id": record["id"], "reason_code": "duplicate_record_id"})
            else:
                seen.add(record["id"])
                retained.append(record)
        collection[:] = retained


def _safe_objects(value: Any, limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value[:limit] if isinstance(item, dict)]


def _known_merge_groups(value: Any, known: dict[str, Any], conflicts: list[dict[str, Any]]) -> list[list[str]]:
    output: list[list[str]] = []
    if not isinstance(value, list):
        return output
    for group in value[:300]:
        if not isinstance(group, list) or len(group) < 2 or any(item not in known for item in group):
            conflicts.append({"reason_code": "unknown_reviewer_merge_id"})
            continue
        unique_group = list(dict.fromkeys(group))
        if len(unique_group) < 2:
            conflicts.append({"reason_code": "invalid_reviewer_merge_group"})
            continue
        output.append(unique_group)
    return output


def _field_index(state: CandidateState) -> dict[str, tuple[str, dict[str, Any]]]:
    output: dict[str, tuple[str, dict[str, Any]]] = {}
    for record in state.employment:
        for name in EMPLOYMENT_FIELDS:
            field = record.get(name)
            if isinstance(field, dict):
                output[field["_id"]] = (name, field)
    for record in state.education:
        for name in EDUCATION_FIELDS:
            field = record.get(name)
            if isinstance(field, dict):
                output[field["_id"]] = (name, field)
    return output


def _apply_merge_groups(
    source: SourceDocument,
    state: CandidateState,
    groups: list[list[str]],
    accepted_ids: set[str],
    conflicts: list[dict[str, Any]],
) -> list[list[str]]:
    applied: list[list[str]] = []
    for group in groups:
        current = state.records
        records = [current.get(record_id) for record_id in group]
        if any(record is None for record in records):
            conflicts.append({"reason_code": "unknown_reviewer_merge_id"})
            continue
        employment_merge = all(record in state.employment for record in records)
        education_merge = all(record in state.education for record in records)
        if not employment_merge and not education_merge:
            conflicts.append({"reason_code": "invalid_reviewer_merge_type"})
            continue
        field_names = EMPLOYMENT_FIELDS if employment_merge else EDUCATION_FIELDS
        canonical = records[0]
        assert canonical is not None
        proposed = deepcopy(canonical)
        for duplicate in records[1:]:
            assert duplicate is not None
            for name in field_names:
                if proposed.get(name) is None and duplicate.get(name) is not None:
                    proposed[name] = deepcopy(duplicate[name])
        relation = _relation_status(source, [proposed[name] for name in field_names if proposed.get(name)])
        if relation != "supported":
            conflicts.append({"record_id": canonical["id"], "reason_code": "invalid_reviewer_merge_relation"})
            continue
        for name in field_names:
            canonical[name] = proposed.get(name)
        canonical["relation_status"] = relation
        if any(record_id in accepted_ids for record_id in group):
            accepted_ids.add(canonical["id"])
        applied.append(group)
    return applied


def _review_status(
    payload: dict[str, Any],
    conflicts: list[Any],
    gaps: list[Any],
    pass_status: str | None,
) -> str:
    if pass_status in {"failed", "unavailable"}:
        return pass_status
    declared = payload.get("status")
    if declared in {"failed", "unavailable"}:
        return declared
    return "partial" if conflicts or gaps or declared == "partial" else "completed"
