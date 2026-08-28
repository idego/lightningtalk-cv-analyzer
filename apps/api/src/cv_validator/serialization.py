from __future__ import annotations

import json
from copy import deepcopy
from typing import TYPE_CHECKING
from typing import Any

from cv_validator.ai.config import AISettings
from cv_validator.ai.domain import AIAnalysisStatus
from cv_validator.ai.request import (
    DETERMINISTIC_OBSERVATIONS_VERSION,
    INPUT_CONTRACT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
)
from cv_validator.domain import Report
from cv_validator.errors import ReportSerializationError

if TYPE_CHECKING:
    from cv_validator.pipeline import PipelineResult


_CHECK_IDS = (
    "contact",
    "education",
    "employment",
    "timeline",
    "duration_claims",
    "relationships",
    "document_quality",
    "protected_boundaries",
)


def serialize_report_payload(report: Report) -> dict[str, Any]:
    payload = report.to_dict()
    _validate_json(payload)
    return payload


def serialize_analysis_payload(
    result: PipelineResult,
    settings: AISettings,
    *,
    analysis_id: str,
) -> dict[str, Any]:
    """Add the AI review envelope without mutating the deterministic report."""
    payload = serialize_report_payload(result.report)
    ai_payload = _serialize_ai_outcome(result, settings)
    payload.update(
        {
            "analysis_id": analysis_id,
            "ai_analysis": ai_payload,
            "checklist": {
                "checks": deepcopy(ai_payload["checklist"]),
                "flags": _serialize_flags(
                    payload["findings"],
                    ai_payload["findings"],
                    payload.get("deterministic", {}).get("observations", []),
                    payload.get("link_inspection"),
                ),
            },
        }
    )
    _validate_json(payload)
    return payload


def _serialize_ai_outcome(
    result: PipelineResult,
    settings: AISettings,
) -> dict[str, Any]:
    outcome = result.ai_outcome
    analysis = (
        deepcopy(outcome.analysis.payload)
        if outcome.status is AIAnalysisStatus.SUCCEEDED
        and outcome.analysis is not None
        else None
    )
    empty_facts = {"contact": [], "education": [], "employment": []}
    empty_checks = {
        check_id: {"checked": False, "issue_count": 0}
        for check_id in _CHECK_IDS
    }
    return {
        "status": outcome.status.value,
        "failure_reason": (
            outcome.failure_reason.value if outcome.failure_reason is not None else None
        ),
        "failure": (
            {
                "stage": outcome.failure_stage,
                "retryable": outcome.retryable,
                "http_status_class": outcome.http_status_class,
                "provider_request_id": outcome.provider_request_id,
                "attempt_count": outcome.attempt_count,
                "latency_ms": outcome.latency_ms,
            }
            if outcome.status is AIAnalysisStatus.FAILED
            else None
        ),
        "manual_retry_available": outcome.status is AIAnalysisStatus.FAILED,
        "attempt_count": outcome.attempt_count,
        "latency_ms": outcome.latency_ms,
        "authority": "ai",
        "source": "document_analyzer",
        "report_language": result.report_language,
        "model": {
            "provider": "openai",
            "configured": settings.model,
            "response": outcome.response_model,
            "reasoning_effort": settings.reasoning_effort,
        },
        "versions": {
            "prompt": PROMPT_VERSION,
            "schema": SCHEMA_VERSION,
            "input_contract": INPUT_CONTRACT_VERSION,
            "deterministic_observations": DETERMINISTIC_OBSERVATIONS_VERSION,
        },
        "usage": deepcopy(outcome.usage),
        "facts": deepcopy(analysis["facts"]) if analysis is not None else empty_facts,
        "findings": deepcopy(analysis["findings"]) if analysis is not None else [],
        "unknowns": deepcopy(analysis["unknowns"]) if analysis is not None else [],
        "research_candidates": (
            deepcopy(analysis["research_candidates"]) if analysis is not None else []
        ),
        "checklist": (
            deepcopy(analysis["checklist"]) if analysis is not None else empty_checks
        ),
        "analysis_limitations": (
            deepcopy(analysis["analysis_limitations"]) if analysis is not None else []
        ),
        "validation_warnings": (
            deepcopy(analysis.get("validation_warnings", []))
            if analysis is not None
            else []
        ),
    }


def _serialize_flags(
    deterministic_findings: list[dict[str, Any]],
    ai_findings: list[dict[str, Any]],
    deterministic_observations: list[dict[str, Any]],
    link_inspection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    finding_categories = {
        finding["signal"] for finding in deterministic_findings
    }
    for index, finding in enumerate(deterministic_findings, start=1):
        flags.append(
            {
                "id": f"code-{index:04d}",
                "source": "code",
                "authority": "code",
                "category": finding["signal"],
                "status": finding["direction"],
                "importance": _deterministic_importance(finding),
                "confidence": "deterministic",
                "observation": finding["observed"],
                "reason": finding["rationale"],
                "presentation_context": {
                    "observed": finding["observed"],
                    "claimed": finding["claimed"],
                    "direction": finding["direction"],
                },
                "limitation": None,
                "evidence": deepcopy(finding.get("evidence", [])),
            }
        )
    for index, finding in enumerate(ai_findings, start=1):
        flags.append(
            {
                "id": f"ai-{index:04d}",
                "source": "ai",
                "authority": finding["authority"],
                "category": finding["category"],
                "status": finding["status"],
                "importance": finding["importance"],
                "confidence": finding["confidence"],
                "observation": finding["observation"],
                "reason": finding["reason"],
                "limitation": finding["limitation"],
                "evidence": deepcopy(finding["evidence"]),
            }
        )
    for index, observation in enumerate(deterministic_observations, start=1):
        if observation["kind"] in finding_categories:
            continue
        flags.append(
            {
                "id": f"code-observation-{index:04d}",
                "source": "code",
                "authority": "code",
                "category": observation["kind"],
                "status": observation["status"],
                "importance": "remaining",
                "confidence": "deterministic",
                "observation": ", ".join(observation["values"]) or observation["kind"],
                "reason": observation["reason"],
                "limitation": None,
                "evidence": deepcopy(observation.get("evidence", [])),
            }
        )
    for index, link in enumerate(
        (link_inspection or {}).get("links", []),
        start=1,
    ):
        if link.get("status") not in {"SUSPICIOUS", "UNAVAILABLE"}:
            continue
        reason_code = link.get("reason_code", "invalid_link_target")
        flags.append(
            {
                "id": f"link-{index:04d}",
                "source": "code",
                "authority": "code",
                "category": f"link_{reason_code}",
                "status": str(link.get("status", "UNAVAILABLE")).lower(),
                "importance": (
                    "attention"
                    if link.get("status") == "SUSPICIOUS"
                    else "remaining"
                ),
                "confidence": "deterministic",
                "observation": link.get("title") or reason_code,
                "reason": _link_flag_reason(reason_code),
                "limitation": (
                    "Review the declared link and its source evidence; this is not a candidate-level verdict."
                ),
                "evidence": deepcopy(link.get("source_evidence", [])),
                "presentation_context": {
                    "observed": link.get("displayed_value"),
                    "claimed": link.get("sanitized_target"),
                    "direction": str(link.get("status", "UNAVAILABLE")).lower(),
                },
            }
        )
    return flags


def _link_flag_reason(reason_code: str) -> str:
    return {
        "hyperlink_target_mismatch": "The displayed value and embedded target point to different normalized destinations.",
        "service_domain_lookalike": "The hostname resembles a recognized profile or portfolio service without being an approved host.",
        "declared_link_not_found": "The declared CV link returned a terminal not-found response.",
        "unrelated_cross_domain_redirect": "The link terminated on a domain unrelated to its original destination.",
        "unsafe_scheme": "The link uses a scheme outside the approved public HTTP(S) boundary.",
        "unsafe_destination": "The link resolves to an address space that the checker does not request.",
        "unsafe_redirect": "A redirect destination failed the same safe public-destination checks.",
    }.get(
        reason_code,
        "The link check produced a deterministic document-review result.",
    )


def deserialize_analysis_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Read old and new stored payloads without requiring new nullable fields."""
    result = deepcopy(payload)
    result.setdefault("structural_audits", None)
    result.setdefault("document_understanding", None)
    if result["document_understanding"] is not None:
        from cv_validator.document_understanding.contract import (
            UnderstandingContractError, sanitize_understanding,
        )
        try:
            result["document_understanding"] = sanitize_understanding(
                result["document_understanding"]
            )
        except UnderstandingContractError:
            result["document_understanding"] = None
    _validate_json(result)
    return result


def _deterministic_importance(finding: dict[str, Any]) -> str:
    if finding.get("score_impact") == "weighted" and finding.get("direction") == "conflicts":
        return "attention"
    if finding.get("score_impact") == "weighted":
        return "worth_knowing"
    if finding.get("signal") in {
        "stated_location_outside_eu",
        "phone_outside_eu",
        "combined_location_outside_eu",
        "small_locality_outside_eu",
    }:
        return "worth_knowing"
    return "remaining"


def _validate_json(payload: dict[str, Any]) -> None:
    try:
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ReportSerializationError(
            "report contains a value that is not JSON-safe"
        ) from exc
