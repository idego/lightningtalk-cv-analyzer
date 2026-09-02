from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

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
) -> tuple[CandidateState, dict[str, Any]]:
    payload = review_payload if isinstance(review_payload, dict) else {}
    known_records = state.records
    known_fields = state.field_ids
    rejected = list(state.rejected)
    conflicts = [
        *state.conflicts,
        *(_bounded_annotation(item) for item in _safe_objects(payload.get("conflicts"), 300)),
    ]
    coverage_gaps = [
        _bounded_annotation(item) for item in _safe_objects(payload.get("coverage_gaps"), 100)
    ]

    rejected_ids: set[str] = set()
    review_rejected: list[dict[str, str]] = []
    for item in _safe_objects(payload.get("rejected_records"), 300):
        record_id = item.get("id")
        reason = item.get("reason_code")
        if record_id not in known_records:
            conflicts.append({"reason_code": "unknown_reviewer_record_id"})
            continue
        if not isinstance(reason, str) or not reason or len(reason) > 128:
            reason = "reviewer_rejected"
        rejected_ids.add(record_id)
        review_rejected.append({"id": record_id, "reason_code": reason})

    # Validated candidates are accepted by default; the reviewer may reject them.
    # `accepted_record_ids` is an optional confirmation kept for contract stability.
    accepted_ids: set[str] = {
        record_id for record_id in known_records if record_id not in rejected_ids
    }
    accepted_requested = payload.get("accepted_record_ids", [])
    if isinstance(accepted_requested, list):
        for record_id in accepted_requested[:300]:
            if record_id not in known_records:
                conflicts.append({"reason_code": "unknown_reviewer_record_id"})

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
            corrections.append({"record_id": record_id, "field_ids": list(dict.fromkeys(field_ids))})

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

    # Merges run after additions so a reviewer may add a candidate and merge it in one pass.
    merge_groups = _known_merge_groups(payload.get("merge_groups"), known_records, conflicts)
    applied_merge_groups = _apply_merge_groups(
        source,
        state,
        merge_groups,
        accepted_ids,
        rejected_ids,
        conflicts,
    )

    surviving = state.records
    added_candidate_ids = [record_id for record_id in added_candidate_ids if record_id in surviving]

    for record in [*state.employment, *state.education]:
        record["status"] = (
            "accepted"
            if record["id"] in accepted_ids
            and record["id"] not in rejected_ids
            and record["relation_status"] == "supported"
            else "ambiguous"
        )

    accepted_final = [
        record["id"]
        for record in [*state.employment, *state.education]
        if record["status"] == "accepted"
    ]
    state.rejected = [*rejected, *review_rejected]
    state.conflicts = conflicts
    review = {
        "status": _review_status(payload, conflicts, coverage_gaps),
        "accepted_ids": accepted_final,
        "rejected": state.rejected,
        "merged_ids": applied_merge_groups,
        "relation_corrections": corrections,
        "added_profile_fields": list(dict.fromkeys(added_profile_fields)),
        "added_candidate_ids": added_candidate_ids,
        "conflicts": conflicts,
        "coverage_gaps": coverage_gaps,
    }
    return state, review


def public_profile(profile: dict[str, Any], *, include_field_ids: bool = False) -> dict[str, Any]:
    return {
        name: (
            [_public_field(item, include_field_ids) for item in value]
            if isinstance(value, list)
            else _public_field(value, include_field_ids)
        )
        for name, value in profile.items()
    }


def public_records(
    records: list[dict[str, Any]],
    field_names: tuple[str, ...],
    *,
    include_field_ids: bool = False,
) -> list[dict[str, Any]]:
    return [
        {
            "id": record["id"],
            "status": record["status"],
            "relation_status": record["relation_status"],
            "added_by_reviewer": record["added_by_reviewer"],
            **{name: _public_field(record.get(name), include_field_ids) for name in field_names},
        }
        for record in records
    ]


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
        if candidate_type == "employment":
            anchored = record["organization"] is not None
            missing_reason = "missing_organization"
        else:
            anchored = record["institution"] is not None or record["certificate"] is not None
            missing_reason = "missing_institution_or_certificate"
        if not anchored:
            rejected.append({"id": record_id, "reason_code": missing_reason})
            continue
        anchors = ("organization",) if candidate_type == "employment" else ("institution", "certificate")
        relation = _detach_far_fields(source, record, field_names, anchors, conflicts)
        record["relation_status"] = relation
        if relation == "invalid":
            rejected.append({"id": record_id, "reason_code": "invalid_record_relation"})
            continue
        output.append(record)
    return output


def _detach_far_fields(
    source: SourceDocument,
    record: dict[str, Any],
    field_names: tuple[str, ...],
    anchors: tuple[str, ...],
    conflicts: list[dict[str, Any]],
) -> str:
    """Drop optional fields cited far from the anchor until the record relation is valid.

    Two-column layouts place dates or locations tens of blocks away from the entry they
    belong to. Losing those fields is better than losing the whole record."""
    block_map = source.by_id()

    def present() -> list[dict[str, Any]]:
        return [record[name] for name in field_names if record[name]]

    relation = _relation_status(source, present())
    while relation == "invalid":
        anchor_orders = [
            block_map[block_id].order
            for name in anchors
            if record.get(name)
            for block_id in record[name]["_block_ids"]
        ]
        if not anchor_orders:
            return relation
        candidates = [
            (
                max(abs(block_map[block_id].order - order) for block_id in record[name]["_block_ids"] for order in anchor_orders),
                name,
            )
            for name in field_names
            if name not in anchors and record.get(name)
        ]
        if not candidates:
            return relation
        _, farthest = max(candidates)
        record[farthest] = None
        conflicts.append({"record_id": record["id"], "field": farthest, "reason_code": "field_detached_from_record"})
        relation = _relation_status(source, present())
    return relation


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
    cited_blocks: list[SourceBlock] = []
    excerpts: list[str] = []
    for citation in evidence:
        if not isinstance(citation, dict):
            return None
        block_id = citation.get("block_id") or citation.get("source_id")
        excerpt = citation.get("excerpt")
        block = blocks.get(block_id)
        if block is None or not isinstance(excerpt, str) or not excerpt or excerpt not in block.text:
            return None
        start = block.text.find(excerpt)
        final_evidence.append(block.evidence(start, start + len(excerpt)))
        block_ids.append(block.id)
        cited_blocks.append(block)
        excerpts.append(excerpt)
    if not _excerpts_cover_value(value, excerpts, cited_blocks):
        return None
    return {
        "_id": field_id,
        "_block_ids": tuple(block_ids),
        "value": value,
        "status": "supported",
        "evidence": final_evidence,
    }


def _excerpts_cover_value(value: str, excerpts: list[str], blocks: list[SourceBlock]) -> bool:
    """A value is literal when one excerpt contains it, or when it is spelled out by
    the excerpts read in order across consecutive blocks (a wrapped line)."""
    if any(value in excerpt for excerpt in excerpts):
        return True
    if len(excerpts) < 2:
        return False
    for previous, current in zip(blocks, blocks[1:]):
        if current.order != previous.order + 1 or current.page_number != previous.page_number:
            return False
        if previous.table_id != current.table_id or previous.row_index != current.row_index:
            return False
    joined = _normalize_space(" ".join(excerpts))
    return _normalize_space(value) in joined


def _normalize_space(text: str) -> str:
    return " ".join(text.split())


def _relation_status(source: SourceDocument, fields: list[dict[str, Any]]) -> str:
    block_map = source.by_id()
    cited = [block_map[block_id] for field in fields for block_id in field["_block_ids"]]
    unique: dict[str, SourceBlock] = {block.id: block for block in cited}
    blocks = list(unique.values())
    if len(blocks) <= 1:
        return "supported"
    table_blocks = [block for block in blocks if block.table_id]
    if table_blocks:
        table_positions = {(block.table_id, block.row_index) for block in table_blocks}
        if len(table_blocks) != len(blocks) or len(table_positions) != 1:
            return "invalid"
        return "supported"
    if (
        len({block.parent_id for block in blocks}) == 1
        and blocks[0].parent_id not in {None, "body", "furniture"}
    ):
        return "supported"
    distance = max(block.order for block in blocks) - min(block.order for block in blocks)
    if distance <= 3:
        return "supported"
    if distance > 6:
        return "invalid"
    return "ambiguous"


def _public_field(field: Any, include_field_id: bool = False) -> Any:
    if not isinstance(field, dict):
        return None
    public = {key: deepcopy(field[key]) for key in ("value", "status", "evidence")}
    if include_field_id:
        public["field_id"] = field["_id"]
    return public


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


MAX_REASON_CODE_LENGTH = 128
MAX_SUMMARY_LENGTH = 200


def _bounded_annotation(item: dict[str, Any]) -> dict[str, Any]:
    """Cap reviewer free text so the persisted report cannot carry CV excerpts."""
    output = deepcopy(item)
    reason = output.get("reason_code")
    if not isinstance(reason, str) or not reason or len(reason) > MAX_REASON_CODE_LENGTH:
        output["reason_code"] = "reviewer_annotation"
    if "summary" in output:
        summary = output["summary"]
        output["summary"] = (
            summary if isinstance(summary, str) and len(summary) <= MAX_SUMMARY_LENGTH else None
        )
    return output


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
    rejected_ids: set[str],
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
        collection = state.employment if employment_merge else state.education
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
        duplicate_ids = {record["id"] for record in records[1:] if record is not None}
        collection[:] = [record for record in collection if record["id"] not in duplicate_ids]
        if any(record_id in accepted_ids for record_id in group):
            accepted_ids.add(canonical["id"])
        accepted_ids.difference_update(duplicate_ids)
        rejected_ids.difference_update(duplicate_ids)
        applied.append(group)
    return applied


def _review_status(payload: dict[str, Any], conflicts: list[Any], gaps: list[Any]) -> str:
    declared = payload.get("status")
    if declared in {"failed", "unavailable"}:
        return declared
    return "partial" if conflicts or gaps or declared == "partial" else "completed"
