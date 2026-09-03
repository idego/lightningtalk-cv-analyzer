from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from jsonschema import Draft202012Validator

from cv_validator.analysis.candidates import (
    EDUCATION_FIELDS,
    EMPLOYMENT_FIELDS,
    apply_review,
    public_profile,
    public_records,
    validate_specialists,
)
from cv_validator.analysis.docling_converter import (
    CONVERTER_VERSION,
    DOCLING_VERSION,
    DoclingTextConverter,
)
from cv_validator.analysis.model_client import (
    REVIEWER_REASONING_EFFORT,
    SPECIALIST_REASONING_EFFORT,
    AnalysisModelClient,
    ModelPassError,
    PASS_SCHEMAS,
)
from cv_validator.analysis.source import SourceDocument
from cv_validator.analysis.strategy import AnalysisInput
from cv_validator.location import (
    Ambiguous,
    LocationResolver,
    PostalCodeResolver,
    Resolved,
    ResolutionLevel,
)
from cv_validator.mechanical import MECHANICAL_VERSION, extract_mechanical
from cv_validator.openai_config import PINNED_OPENAI_MODEL
from cv_validator.operations import utc_now
from cv_validator.usage import normalize_usage


STRATEGY_NAME = "document-analysis"
STRATEGY_VERSION = "document-analysis-v3"
MAX_PASS_ATTEMPTS = 2
EU_COUNTRY_CODES = {
    "AT", "BE", "BG", "HR", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HU", "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL",
    "PT", "RO", "SE", "SI", "SK",
}


@dataclass(frozen=True)
class _PassOutcome:
    payload: dict[str, Any]
    status: str
    attempt_count: int
    latency_ms: int
    failure_reason: str | None
    usage: Any
    model: str | None
    section_status: str | None = None

    def status_payload(self, effort: str) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "attempt_count": self.attempt_count,
            "latency_ms": self.latency_ms,
            "failure_reason": self.failure_reason,
            "usage": _bounded_usage(self.usage),
            "model": self.model,
            "reasoning_effort": effort,
        }
        if self.section_status is not None:
            payload["section_status"] = self.section_status
        return payload


class DocumentAnalysisStrategy:
    name = STRATEGY_NAME
    version = STRATEGY_VERSION

    def __init__(
        self,
        *,
        converter: DoclingTextConverter | None = None,
        client: AnalysisModelClient | None = None,
        location_resolver: LocationResolver | None = None,
        postal_code_resolver: PostalCodeResolver | None = None,
    ) -> None:
        self._converter = converter or DoclingTextConverter()
        self._client = client
        self._location_resolver = location_resolver
        self._postal_code_resolver = postal_code_resolver

    @property
    def ready(self) -> bool:
        return self._client is not None

    @property
    def readiness_reason(self) -> str | None:
        return None if self.ready else "ai_client_unavailable"

    def analyze(self, request: AnalysisInput) -> dict[str, Any]:
        if not self.ready:
            from cv_validator.analysis.strategy import AnalysisStrategyUnavailable
            raise AnalysisStrategyUnavailable("analysis_strategy_unavailable")
        analysis_started = perf_counter()
        conversion_started = perf_counter()
        try:
            source = self._converter.convert(
                request.content,
                request.filename,
                request.source_format,
            )
        except Exception:
            if request.recorder:
                request.recorder.emit(
                    "conversion_failed",
                    operation="docling_conversion",
                    outcome="failed",
                    error_code="conversion_failed",
                    latency_ms=int((perf_counter() - conversion_started) * 1000),
                )
            raise
        if request.recorder:
            request.recorder.emit(
                "conversion_completed",
                operation="docling_conversion",
                outcome="completed",
                latency_ms=int((perf_counter() - conversion_started) * 1000),
            )
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix="cv-base") as pool:
            pass_futures = {
                name: pool.submit(self._run_pass, name, source, None, request.recorder)
                for name in ("profile", "employment", "education")
            }
            mechanical_future = pool.submit(extract_mechanical, source.blocks)
            outcomes = {name: future.result() for name, future in pass_futures.items()}
            mechanical = mechanical_future.result()

        state = validate_specialists(
            source,
            outcomes["profile"].payload,
            outcomes["employment"].payload,
            outcomes["education"].payload,
        )
        if request.recorder:
            rejection_histogram = Counter(
                item.get("reason_code", "unknown") for item in state.rejected
            )
            request.recorder.emit(
                "validation_completed",
                operation="candidate_validation",
                outcome="completed",
                raw_candidate_count=sum(
                    len(outcomes[name].payload.get("records", []))
                    for name in ("employment", "education")
                    if isinstance(outcomes[name].payload.get("records", []), list)
                ),
                evidence_valid_count=len(state.employment) + len(state.education),
                evidence_invalid_count=len(state.rejected),
                rejection_reason_histogram=dict(rejection_histogram),
            )
        review_context = {
            "profile": public_profile(state.profile, include_field_ids=True),
            "employment": public_records(state.employment, EMPLOYMENT_FIELDS, include_field_ids=True),
            "education": public_records(state.education, EDUCATION_FIELDS, include_field_ids=True),
            "rejected": state.rejected,
            "conflicts": state.conflicts,
            "mechanical": mechanical,
            "pass_statuses": {name: outcome.status for name, outcome in outcomes.items()},
        }
        review_outcome = self._run_pass("review", source, review_context, request.recorder)
        state, review = apply_review(source, state, review_outcome.payload)
        if request.recorder:
            reviewer_rejected = review_outcome.payload.get("rejected_records", [])
            if not isinstance(reviewer_rejected, list):
                reviewer_rejected = []
            request.recorder.emit(
                "review_completed",
                operation="review",
                outcome=review["status"],
                extracted_count=len(state.employment) + len(state.education),
                rejected_count=len(reviewer_rejected),
                corrected_count=len(review["relation_corrections"]),
                added_count=len(review["added_candidate_ids"]),
                research_eligible_count=sum(
                    record.get("status") == "accepted" and record.get("relation_status") == "supported"
                    for record in [*state.employment, *state.education]
                ),
            )
        mechanical = _enrich_mechanical(
            deepcopy(mechanical),
            public_profile(state.profile),
            self._location_resolver,
            self._postal_code_resolver,
        )
        pass_statuses = {
            name: outcome.status_payload(SPECIALIST_REASONING_EFFORT)
            for name, outcome in outcomes.items()
        }
        pass_statuses["review"] = review_outcome.status_payload(REVIEWER_REASONING_EFFORT)
        statuses = [outcome.status for outcome in outcomes.values()]
        status = _overall_status(statuses, review["status"])
        total_usage = _aggregate_usage([*outcomes.values(), review_outcome])
        report = {
            "contract_version": "base-analysis-v2",
            "strategy": {"name": self.name, "version": self.version},
            "source": {
                "format": request.source_format.value,
                "sha256": request.sha256,
                "identity": source.identity,
                "conversion_status": "completed",
                "block_count": len(source.blocks),
            },
            "base_analysis": {
                "status": status,
                "profile": public_profile(state.profile),
                "employment": public_records(state.employment, EMPLOYMENT_FIELDS),
                "education": public_records(state.education, EDUCATION_FIELDS),
                "pass_statuses": pass_statuses,
                "review": review,
            },
            "mechanical": mechanical,
            "research": {"status": "pending_automatic_start"},
            "limitations": _limitations(statuses, review),
            "versions": {
                "contract": "base-analysis-v2",
                "strategy": self.version,
                "docling": DOCLING_VERSION,
                "converter": CONVERTER_VERSION,
                "mechanical": MECHANICAL_VERSION,
                "model": PINNED_OPENAI_MODEL,
                "postal_reference_data": (
                    self._postal_code_resolver.reference_data_version.version
                    if self._postal_code_resolver is not None
                    else "unavailable"
                ),
            },
            "usage": {
                **total_usage,
                "latency_ms": int((perf_counter() - analysis_started) * 1000),
                "live_model_calls": bool(getattr(self._client, "is_live", False)),
            },
        }
        if request.recorder:
            request.recorder.emit(
                "assembly_completed",
                operation="report_assembly",
                outcome="completed",
                accepted_count=len(review["accepted_ids"]),
                ambiguous_count=sum(
                    item.get("status") == "ambiguous"
                    for item in [*report["base_analysis"]["employment"], *report["base_analysis"]["education"]]
                ),
                coverage_gaps_count=len(review["coverage_gaps"]),
            )
        return report

    def _run_pass(
        self,
        name: str,
        source: SourceDocument,
        context: dict[str, Any] | None = None,
        recorder: Any = None,
    ) -> _PassOutcome:
        started = perf_counter()
        if self._client is None:
            return _PassOutcome({}, "unavailable", 0, 0, "ai_disabled", {}, None)
        failure = "pass_failed"
        failure_usage: dict[str, Any] = {}
        failure_model: str | None = None
        for attempt in range(1, MAX_PASS_ATTEMPTS + 1):
            attempt_started_at = utc_now()
            attempt_started = perf_counter()
            if recorder:
                recorder.emit(
                    "ai_pass_started",
                    operation=name,
                    category="base_analysis",
                    provider="openai",
                    configured_model=PINNED_OPENAI_MODEL,
                    reasoning_effort=REVIEWER_REASONING_EFFORT if name == "review" else SPECIALIST_REASONING_EFFORT,
                    attempt=attempt,
                    outcome="started",
                )
            try:
                response = self._client.run(name, source, context)
                if not Draft202012Validator(PASS_SCHEMAS[name]).is_valid(response.payload):
                    raise ModelPassError(
                        "invalid_schema",
                        usage=response.usage,
                        model=response.model,
                    )
                latency_ms = int((perf_counter() - attempt_started) * 1000)
                if recorder:
                    recorder.record_ai_attempt(
                        operation=name,
                        category="base_analysis",
                        provider="openai",
                        configured_model=PINNED_OPENAI_MODEL,
                        response_model=response.model,
                        reasoning_effort=REVIEWER_REASONING_EFFORT if name == "review" else SPECIALIST_REASONING_EFFORT,
                        attempt=attempt,
                        outcome="completed",
                        started_at=attempt_started_at,
                        completed_at=utc_now(),
                        latency_ms=latency_ms,
                        usage=response.usage,
                    )
                return _PassOutcome(
                    response.payload,
                    "completed",
                    attempt,
                    int((perf_counter() - started) * 1000),
                    None,
                    response.usage,
                    response.model,
                )
            except ModelPassError as exc:
                failure = exc.code
                failure_usage = exc.usage
                failure_model = exc.model
            except Exception:
                failure = "client_error"
                failure_usage = {}
                failure_model = None
            if recorder:
                recorder.record_ai_attempt(
                    operation=name,
                    category="base_analysis",
                    provider="openai",
                    configured_model=PINNED_OPENAI_MODEL,
                    response_model=failure_model,
                    reasoning_effort=REVIEWER_REASONING_EFFORT if name == "review" else SPECIALIST_REASONING_EFFORT,
                    attempt=attempt,
                    outcome="failed",
                    error_code=failure,
                    started_at=attempt_started_at,
                    completed_at=utc_now(),
                    latency_ms=int((perf_counter() - attempt_started) * 1000),
                    usage=failure_usage,
                )
        return _PassOutcome(
            {},
            "failed",
            MAX_PASS_ATTEMPTS,
            int((perf_counter() - started) * 1000),
            failure,
            failure_usage,
            failure_model,
        )


def _enrich_mechanical(
    mechanical: dict[str, Any],
    profile: dict[str, Any],
    resolver: LocationResolver | None,
    postal_resolver: PostalCodeResolver | None = None,
) -> dict[str, Any]:
    declared = profile.get("declared_location")
    declared_evidence = deepcopy((declared or {}).get("evidence", []))
    resolutions: list[dict[str, Any]] = []
    declared_country_code: str | None = None
    city: str | None = None
    country: str | None = None
    if isinstance(declared, dict) and declared.get("status") == "supported":
        city, country = _declared_location_parts(declared["value"])
        item: dict[str, Any] = {
            "subject": "declared_location",
            "value": declared["value"],
            "city": city,
            "country": country,
            "evidence": declared_evidence,
        }
        if resolver is None:
            item.update({"status": "unavailable", "city_country_relationship": "unavailable"})
            resolutions.append(item)
        else:
            city_outcome = resolver.resolve(city, level=ResolutionLevel.LOCALITY)
            country_outcome = (
                resolver.resolve(country, level=ResolutionLevel.COUNTRY)
                if country
                else None
            )
            if isinstance(city_outcome, Resolved):
                item.update({
                    "status": "resolved",
                    "canonical_name": city_outcome.resolution.canonical_name,
                    "city_country_code": city_outcome.resolution.country_code,
                })
                declared_country_code = city_outcome.resolution.country_code
            elif isinstance(city_outcome, Ambiguous):
                item["status"] = "ambiguous"
                item["candidate_country_codes"] = sorted({
                    match.country_code for match in city_outcome.matches
                })
                if city_outcome.common_resolution is not None:
                    declared_country_code = city_outcome.common_resolution.country_code
            else:
                item["status"] = "unresolved"
            if isinstance(country_outcome, Resolved):
                explicit_country_code = country_outcome.resolution.country_code
                item["resolved_country_name"] = country_outcome.resolution.canonical_name
                item["country_code"] = explicit_country_code
                declared_country_code = explicit_country_code
                city_codes = {
                    match.country_code for match in city_outcome.matches
                }
                if not city_codes:
                    item["city_country_relationship"] = "unresolved"
                elif explicit_country_code in city_codes:
                    item["city_country_relationship"] = (
                        "same" if isinstance(city_outcome, Resolved) else "ambiguous"
                    )
                else:
                    item["city_country_relationship"] = "different"
            elif country:
                item["country_status"] = (
                    "ambiguous" if isinstance(country_outcome, Ambiguous) else "unresolved"
                )
                item["city_country_relationship"] = "unresolved"
            else:
                item["country_code"] = declared_country_code
                item["city_country_relationship"] = "not_applicable"
            item["reference_data_version"] = city_outcome.reference_data_version.version
            resolutions.append(item)

    accepted_postal = []
    for candidate in mechanical["postal_candidates"]:
        evidence = candidate.get("evidence", [])
        if not _address_evidence_is_related(
            declared_evidence, evidence
        ) or not city or not country:
            continue
        accepted = deepcopy(candidate)
        accepted.update({
            "ownership_status": "accepted_declared_address",
            "city": city,
            "country": country,
            "country_code": declared_country_code,
            "address_evidence": declared_evidence,
        })
        if postal_resolver is None or declared_country_code is None:
            accepted["validation"] = {
                "status": "unavailable",
                "reason": "postal_reference_data_unavailable",
            }
        else:
            postal = postal_resolver.validate(
                str(candidate["value"]),
                city=city,
                country_code=declared_country_code,
            )
            accepted["validation"] = {
                "status": postal.status,
                "matched_places": list(postal.matched_places),
                "reference_data_version": postal.reference_data_version.version,
            }
        accepted_postal.append(accepted)
    mechanical["accepted_postal_addresses"] = accepted_postal
    mechanical["location_resolution"] = resolutions
    phone_sources = [
        {
            "kind": "phone_prefix",
            "country_code": phone["country_code"],
            "value": phone.get("value"),
            "evidence": deepcopy(phone.get("evidence", [])),
        }
        for phone in mechanical["phones"]
        if isinstance(phone.get("country_code"), str)
    ]
    location_sources = ([{
        "kind": "declared_location",
        "country_code": declared_country_code,
        "value": declared.get("value") if isinstance(declared, dict) else None,
        "evidence": declared_evidence,
    }] if declared_country_code else []) + phone_sources
    phone_countries = {source["country_code"] for source in phone_sources}
    country_codes = {declared_country_code} if declared_country_code else set()
    all_countries = country_codes | phone_countries
    mechanical["eu_status"] = (
        {
            "countries": sorted(all_countries),
            "inside_eu": sorted(code for code in all_countries if code in EU_COUNTRY_CODES),
            "outside_eu": sorted(code for code in all_countries if code not in EU_COUNTRY_CODES),
            "sources": location_sources,
            "primary_source": "declared_location" if declared_country_code else "phone_prefix",
            "informational_only": True,
        }
        if all_countries
        else None
    )
    mechanical["comparisons"] = _direct_comparisons(country_codes, phone_countries)
    return mechanical


def _record_signature(record: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (name, " ".join(field["value"].casefold().split()))
        for name, field in sorted(record.items())
        if isinstance(field, dict) and isinstance(field.get("value"), str)
    )


def _declared_location_parts(value: str) -> tuple[str, str | None]:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if len(parts) < 2:
        return value.strip(), None
    return parts[0], parts[-1]


def _address_evidence_is_related(
    location_evidence: list[dict[str, Any]],
    postal_evidence: list[dict[str, Any]],
) -> bool:
    for location_item in location_evidence:
        for postal_item in postal_evidence:
            if location_item.get("source_id") != postal_item.get("source_id"):
                continue
            offsets = (
                location_item.get("start_offset"),
                location_item.get("end_offset"),
                postal_item.get("start_offset"),
                postal_item.get("end_offset"),
            )
            if not all(isinstance(value, int) for value in offsets):
                continue
            location_start, location_end, postal_start, postal_end = offsets
            gap = max(location_start, postal_start) - min(location_end, postal_end)
            if gap <= 64:
                return True
    return False


def _direct_comparisons(declared: set[str], phones: set[str]) -> list[dict[str, Any]]:
    if not declared or not phones:
        return []
    return [{
        "kind": "declared_location_phone_country",
        "declared_country_codes": sorted(declared),
        "phone_country_codes": sorted(phones),
        "relationship": "same" if declared == phones else "different",
        "decision_support_only": True,
    }]


def _overall_status(specialists: list[str], review: str) -> str:
    if all(status in {"failed", "unavailable"} for status in specialists):
        return "failed" if all(status == "failed" for status in specialists) else "unavailable"
    if review != "completed" or any(status != "completed" for status in specialists):
        return "partial"
    return "completed"


def _limitations(statuses: list[str], review: dict[str, Any]) -> list[str]:
    limitations = [
        "Decision support only; this analysis does not verify identity, residence, honesty, nationality, or work eligibility."
    ]
    if any(status != "completed" for status in statuses):
        limitations.append("One or more specialist passes were unavailable or failed; supported results from other passes were retained.")
    if review["coverage_gaps"]:
        limitations.append("The reviewer identified source areas that could not be safely materialized as candidates.")
    return limitations


def _bounded_usage(usage: Any) -> dict[str, int]:
    return normalize_usage(usage)


def _aggregate_usage(outcomes: list[_PassOutcome]) -> dict[str, int]:
    totals = {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }
    for outcome in outcomes:
        for key, value in _bounded_usage(outcome.usage).items():
            totals[key] += value
    return totals
