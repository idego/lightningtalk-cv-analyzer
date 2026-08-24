#!/usr/bin/env python3
"""Private-corpus document-analysis eval with private-path output enforcement."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, NamedTuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api/src"))

from cv_validator.ai.request import (  # noqa: E402
    DETERMINISTIC_OBSERVATIONS_VERSION,
    INPUT_CONTRACT_VERSION,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    format_document_analysis_input,
    format_line_referenced_markdown,
)
from cv_validator.ai.validation import (  # noqa: E402
    DocumentAnalysisValidationError,
    REQUIRED_CHECK_IDS,
    validate_document_analysis_payload,
)
from cv_validator.ingestion import SourcePage  # noqa: E402

PRIVATE_EVAL_ROOT = (ROOT / "data/ai-eval").resolve()
CONTRACT_ROOT = ROOT / "apps/api/src/cv_validator/ai/contracts"
PROMPT_PATH = CONTRACT_ROOT / "prompt.md"
SCHEMA_PATH = CONTRACT_ROOT / "document-analysis.schema.json"
CHECK_IDS = set(REQUIRED_CHECK_IDS)
MANUAL_LABELS = {"true positive", "przydatne „warto wiedzieć”", "duplikat", "nadinterpretacja", "artefakt parsowania/flatteningu"}
ACCEPTED_ADDITIONAL_LABELS = {"true positive", "przydatne „warto wiedzieć”"}
MAX_EVAL_CASES = 4


class EvalCaseInput(NamedTuple):
    pages: dict[str, str]
    deterministic_observations: dict[str, Any]
    request_text: str


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def require_private_path(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=False)
    try:
        resolved.relative_to(PRIVATE_EVAL_ROOT)
    except ValueError as error:
        raise ValueError(f"{label} must stay inside ignored {PRIVATE_EVAL_ROOT}") from error
    return resolved


def write_private_json(path: Path, value: Any) -> None:
    destination = require_private_path(path, "output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def validate_manifest_limits(manifest: dict[str, Any]) -> None:
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("eval manifest must contain at least one case")
    if len(cases) > MAX_EVAL_CASES:
        raise ValueError(f"eval manifest may contain at most {MAX_EVAL_CASES} cases")


def backend_output_limit_metadata(
    backend: str,
    requested_limit: int | None,
) -> dict[str, Any]:
    if backend == "responses":
        if requested_limit is None or requested_limit < 1:
            raise ValueError(
                "--max-output-tokens is required and must be positive for Responses"
            )
        return {
            "max_output_tokens": requested_limit,
            "output_limit_enforcement": "enforced",
        }
    if backend == "codex":
        return {
            "max_output_tokens": None,
            "output_limit_enforcement": "not_enforced",
        }
    raise ValueError("unsupported eval backend")


def load_case_input(case: dict[str, Any], manifest_path: Path) -> EvalCaseInput:
    raw_pages = case.get("pages")
    if not isinstance(raw_pages, list) or not raw_pages:
        raise ValueError("each eval case requires one or more pages")
    pages: dict[str, str] = {}
    for page in raw_pages:
        if not isinstance(page, dict):
            raise ValueError("eval pages must be objects")
        page_id = page.get("page_id")
        input_path = page.get("input")
        if not isinstance(page_id, str) or not page_id or not isinstance(input_path, str):
            raise ValueError("each eval page requires page_id and input")
        if page_id in pages:
            raise ValueError("eval page IDs must be unique within a case")
        source_path = require_private_path(
            manifest_path.parent / input_path,
            "eval page input",
        )
        pages[page_id] = source_path.read_text(encoding="utf-8")

    observations_path_value = case.get("deterministic_observations")
    if not isinstance(observations_path_value, str):
        raise ValueError("each eval case requires deterministic_observations")
    observations_path = require_private_path(
        manifest_path.parent / observations_path_value,
        "deterministic observations",
    )
    observations = load_json(observations_path)
    if (
        not isinstance(observations, dict)
        or observations.get("contract_version")
        != DETERMINISTIC_OBSERVATIONS_VERSION
        or not isinstance(observations.get("deterministic_ruleset_version"), str)
        or not isinstance(observations.get("observations"), list)
    ):
        raise ValueError("deterministic observations do not match the versioned contract")

    markdown = format_line_referenced_markdown(
        tuple(
            SourcePage(page_id, page_number, text)
            for page_number, (page_id, text) in enumerate(pages.items(), start=1)
        )
    )
    return EvalCaseInput(
        pages=pages,
        deterministic_observations=observations,
        request_text=format_document_analysis_input(markdown, observations),
    )


def validate_result(
    result: Any,
    pages: dict[str, str],
) -> list[str]:
    _, errors = validate_and_materialize_result(result, pages)
    return errors


def validate_and_materialize_result(
    result: Any,
    pages: dict[str, str],
) -> tuple[Any, list[str]]:
    try:
        validated = validate_document_analysis_payload(
            result,
            pages=pages,
            deterministic_observations_version=DETERMINISTIC_OBSERVATIONS_VERSION,
        )
    except DocumentAnalysisValidationError as error:
        return result, [str(error)]
    return validated.payload, []


def evidence_is_exact(evidence: dict[str, Any], pages: dict[str, str]) -> bool:
    source_line = source_line_for_evidence(evidence, pages)
    excerpt = evidence.get("excerpt")
    if source_line is not None:
        return isinstance(excerpt, str) and excerpt == source_line
    page_id = evidence.get("page_id")
    return (
        isinstance(page_id, str)
        and isinstance(excerpt, str)
        and bool(excerpt)
        and page_id in pages
        and excerpt in pages[page_id]
    )


def source_line_for_evidence(
    evidence: dict[str, Any],
    pages: dict[str, str],
) -> str | None:
    page_id = evidence.get("page_id")
    line_id = evidence.get("line_id")
    if not isinstance(page_id, str) or not isinstance(line_id, str):
        return None
    page_text = pages.get(page_id)
    if not isinstance(page_text, str):
        return None
    page_number = tuple(pages).index(page_id) + 1
    source_line = next(
        (
            line
            for line in SourcePage(page_id, page_number, page_text).lines
            if line.line_id == line_id
        ),
        None,
    )
    return source_line.text if source_line is not None and source_line.text else None


def line_reference_is_valid(
    evidence: dict[str, Any],
    pages: dict[str, str],
) -> bool:
    if isinstance(evidence.get("line_id"), str):
        return source_line_for_evidence(evidence, pages) is not None
    return evidence_is_exact(evidence, pages)


def evidence_items_by_section(
    result: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    fact_evidence = [
        evidence
        for fact_group in result.get("facts", {}).values()
        if isinstance(fact_group, list)
        for fact in fact_group
        if isinstance(fact, dict)
        for evidence in fact.get("evidence", [])
        if isinstance(evidence, dict)
    ]
    finding_evidence = [
        evidence
        for finding in result.get("findings", [])
        if isinstance(finding, dict)
        for evidence in finding.get("evidence", [])
        if isinstance(evidence, dict)
    ]
    research_evidence = [
        candidate["evidence"]
        for candidate in result.get("research_candidates", [])
        if isinstance(candidate, dict)
        and isinstance(candidate.get("evidence"), dict)
    ]
    return {
        "facts": fact_evidence,
        "findings": finding_evidence,
        "research_candidates": research_evidence,
    }


def dematerialize_code_owned_excerpts(
    result: dict[str, Any],
    pages: dict[str, str],
) -> dict[str, Any]:
    candidate = deepcopy(result)
    source_lines = {
        line.line_id: (page.page_id, line.text)
        for page_number, (page_id, text) in enumerate(pages.items(), start=1)
        for page in (SourcePage(page_id, page_number, text),)
        for line in page.lines
    }
    for evidence_items in evidence_items_by_section(candidate).values():
        for evidence in evidence_items:
            source = source_lines.get(evidence.get("line_id"))
            if (
                source is not None
                and source[0] == evidence.get("page_id")
                and source[1] == evidence.get("excerpt")
            ):
                evidence["excerpt"] = None
    return candidate


def call_responses(model: str, reasoning: str, instructions: str, document: str, schema: dict[str, Any], max_output_tokens: int) -> tuple[dict[str, Any], dict[str, Any], str]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --backend responses")
    from openai import OpenAI

    payload = {
        "model": model,
        "reasoning": {"effort": reasoning},
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": document}]}],
        "text": {"format": {"type": "json_schema", "name": "document_analysis", "strict": True, "schema": schema}},
        "tools": [],
        "store": False,
        "max_output_tokens": max_output_tokens,
    }
    client = OpenAI(api_key=api_key, timeout=120.0, max_retries=0)
    try:
        response = client.responses.create(**payload)
    except Exception:
        raise RuntimeError("Responses API request failed") from None
    if not response.output_text:
        raise RuntimeError("Responses API returned no output text")
    usage = response.usage.model_dump() if response.usage is not None else {}
    return json.loads(response.output_text), usage, response.model


def call_codex(model: str, reasoning: str, prompt: str, schema_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check", "--sandbox", "read-only", "--cd", "/tmp", "--model", model, "-c", f'model_reasoning_effort="{reasoning}"', "--output-schema", str(schema_path), "--json", "-"]
    completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=240, check=False, cwd="/tmp")
    if completed.returncode:
        raise RuntimeError(f"codex exec failed ({completed.returncode}); raw model output was not printed")
    message: str | None = None
    usage: dict[str, Any] = {}
    for line in completed.stdout.splitlines():
        event = json.loads(line)
        if event.get("type") == "item.completed" and event.get("item", {}).get("type") == "agent_message":
            message = event["item"].get("text")
        event_usage = event.get("usage") or event.get("token_usage")
        if isinstance(event_usage, dict):
            usage = event_usage
    if not message:
        raise RuntimeError("codex exec returned no agent message")
    return json.loads(message), usage


def matches(expected: dict[str, Any], finding: dict[str, Any]) -> bool:
    if expected["category"] != finding.get("category"):
        return False
    expected_status = expected.get("status")
    if expected_status is not None and expected_status != finding.get("status"):
        return False
    needle = expected.get("evidence_contains", "").casefold()
    excerpts = " ".join(
        item.get("excerpt") or "" for item in finding.get("evidence", [])
    ).casefold()
    return not needle or needle in excerpts


def _maximum_expected_finding_matches(
    expected: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[int, int]:
    """Return a one-to-one expected-index to finding-index matching."""
    finding_to_expected: dict[int, int] = {}

    def assign(expected_index: int, seen: set[int]) -> bool:
        for finding_index, finding in enumerate(findings):
            if finding_index in seen or not matches(expected[expected_index], finding):
                continue
            seen.add(finding_index)
            previous = finding_to_expected.get(finding_index)
            if previous is None or assign(previous, seen):
                finding_to_expected[finding_index] = expected_index
                return True
        return False

    for expected_index in range(len(expected)):
        assign(expected_index, set())
    return {
        expected_index: finding_index
        for finding_index, expected_index in finding_to_expected.items()
    }


def score(case: dict[str, Any], result: dict[str, Any], pages: dict[str, str]) -> dict[str, Any]:
    expected = case["expected_findings"]
    findings = result.get("findings", [])
    matching = _maximum_expected_finding_matches(expected, findings)
    matched_expected = set(matching)
    matched_findings = set(matching.values())
    unexpected_finding_indices = [
        index for index in range(len(findings)) if index not in matched_findings
    ]
    evidence_sections = evidence_items_by_section(result)
    evidence_items = evidence_sections["findings"]
    accurate = sum(evidence_is_exact(evidence, pages) for evidence in evidence_items)
    all_evidence_items = [
        evidence
        for section in evidence_sections.values()
        for evidence in section
    ]
    all_accurate = sum(
        evidence_is_exact(evidence, pages) for evidence in all_evidence_items
    )
    valid_line_references = sum(
        line_reference_is_valid(evidence, pages)
        for evidence in all_evidence_items
    )
    unsupported_findings = sum(
        not finding.get("evidence")
        or any(
            not line_reference_is_valid(evidence, pages)
            for evidence in finding.get("evidence", [])
        )
        for finding in findings
    )
    serialized = json.dumps(result, ensure_ascii=False).casefold()
    forbidden_hits = [term for term in case.get("forbidden_output_terms", []) if term.casefold() in serialized]
    return {
        "expected_count": len(expected),
        "matched_expected_count": len(matched_expected),
        "recall": len(matched_expected) / len(expected) if expected else 1.0,
        "finding_count": len(findings),
        "unsupported_finding_count": unsupported_findings,
        "unexpected_finding_count": len(unexpected_finding_indices),
        "unexpected_finding_indices": unexpected_finding_indices,
        "finding_evidence_exact_match_count": accurate,
        "finding_evidence_item_count": len(evidence_items),
        "finding_evidence_exact_match_accuracy_page_aware": accurate / len(evidence_items) if evidence_items else 1.0,
        "all_evidence_exact_match_count": all_accurate,
        "all_evidence_item_count": len(all_evidence_items),
        "invalid_evidence_item_count": len(all_evidence_items) - all_accurate,
        "all_evidence_exact_match_accuracy_page_aware": all_accurate / len(all_evidence_items) if all_evidence_items else 1.0,
        "line_reference_valid_count": valid_line_references,
        "line_reference_item_count": len(all_evidence_items),
        "line_reference_validity": valid_line_references / len(all_evidence_items) if all_evidence_items else 1.0,
        "forbidden_output_hits": forbidden_hits,
    }


def baseline_is_acceptable(reports: list[dict[str, Any]]) -> bool:
    """Apply the agreed strict gate without treating recall as precision."""
    for report in reports:
        metrics = report["metrics"]
        if (
            report["validation_errors"]
            or metrics["recall"] < 1.0
            or metrics["unsupported_finding_count"] != 0
            or metrics.get("invalid_evidence_item_count", 1) != 0
            or metrics.get("line_reference_validity", 0.0) < 1.0
            or metrics["finding_evidence_exact_match_accuracy_page_aware"] < 1.0
            or metrics["forbidden_output_hits"]
        ):
            return False
        unexpected = set(metrics.get("unexpected_finding_indices", []))
        reviews = {
            review["finding_index"]: review["classification"]
            for review in report.get("manual_review", [])
        }
        if set(reviews) != unexpected or any(
            reviews[index] not in ACCEPTED_ADDITIONAL_LABELS
            for index in unexpected
        ):
            return False
    return True


def parse_manual_review(path: Path) -> list[dict[str, Any]]:
    review_path = require_private_path(path, "manual review")
    reviews: list[dict[str, Any]] = []
    current_case: str | None = None
    current_index: int | None = None
    checked: list[str] = []

    def finish() -> None:
        nonlocal checked
        if current_case is None or current_index is None:
            return
        if len(checked) != 1:
            raise ValueError(f"{current_case} finding {current_index} must have exactly one checked classification")
        reviews.append({"case_id": current_case, "finding_index": current_index, "classification": checked[0]})
        checked = []

    for line in review_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and not line.startswith("### "):
            finish()
            current_case = line[3:].strip()
            current_index = None
        elif match := re.match(r"### \d+\. Finding index (\d+):", line):
            finish()
            current_index = int(match.group(1))
        elif match := re.match(r"- \[[xX]\] (.+)", line):
            label = match.group(1)
            if label not in MANUAL_LABELS:
                raise ValueError(f"unknown manual-review classification: {label}")
            checked.append(label)
    finish()
    return reviews


def attach_manual_review(report: dict[str, Any], reviews: list[dict[str, Any]]) -> None:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for review in reviews:
        by_case.setdefault(review["case_id"], []).append(review)
    for case_report in report["cases"]:
        case_reviews = by_case.get(case_report["case_id"], [])
        finding_count = len(case_report["result"].get("findings", []))
        for review in case_reviews:
            if review["finding_index"] >= finding_count:
                raise ValueError(f"manual review points outside findings for {case_report['case_id']}")
        case_report["manual_review"] = sorted(case_reviews, key=lambda item: item["finding_index"])


def token_value(usage: dict[str, Any], *names: str) -> int | None:
    for name in names:
        value = usage.get(name)
        if isinstance(value, int):
            return value
    return None


def summarize(reports: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [report for report in reports if not report["validation_errors"]]
    expected_count = sum(report["metrics"]["expected_count"] for report in reports)
    matched_expected_count = sum(
        report["metrics"]["matched_expected_count"] for report in reports
    )
    accepted_matched_expected_count = sum(
        report["metrics"]["matched_expected_count"] for report in valid
    )
    finding_evidence_count = sum(
        report["metrics"]["finding_evidence_item_count"] for report in reports
    )
    finding_evidence_exact_count = sum(
        report["metrics"]["finding_evidence_exact_match_count"]
        for report in reports
    )
    all_evidence_count = sum(
        report["metrics"]["all_evidence_item_count"] for report in reports
    )
    all_evidence_exact_count = sum(
        report["metrics"]["all_evidence_exact_match_count"] for report in reports
    )
    line_reference_count = sum(
        report["metrics"].get(
            "line_reference_item_count",
            report["metrics"]["all_evidence_item_count"],
        )
        for report in reports
    )
    valid_line_reference_count = sum(
        report["metrics"].get(
            "line_reference_valid_count",
            report["metrics"]["all_evidence_exact_match_count"],
        )
        for report in reports
    )
    summary: dict[str, Any] = {
        "case_count": len(reports),
        "valid_case_count": len(valid),
        "macro_recall": sum(report["metrics"]["recall"] for report in reports) / len(reports),
        "expected_finding_micro_recall": matched_expected_count / expected_count if expected_count else 1.0,
        "accepted_expected_finding_micro_recall": accepted_matched_expected_count / expected_count if expected_count else 1.0,
        "recall_is_not_precision": True,
        "unsupported_finding_count": sum(report["metrics"]["unsupported_finding_count"] for report in reports),
        "unexpected_finding_count": sum(report["metrics"]["unexpected_finding_count"] for report in reports),
        "finding_evidence_exact_match_accuracy_page_aware": finding_evidence_exact_count / finding_evidence_count if finding_evidence_count else 1.0,
        "all_evidence_exact_match_accuracy_page_aware": all_evidence_exact_count / all_evidence_count if all_evidence_count else 1.0,
        "invalid_evidence_item_count": all_evidence_count - all_evidence_exact_count,
        "line_reference_validity": valid_line_reference_count / line_reference_count if line_reference_count else 1.0,
        "total_latency_seconds": sum(report["latency_seconds"] for report in reports),
        "estimated_cost_usd": None if any(report["estimated_cost_usd"] is None for report in reports) else sum(report["estimated_cost_usd"] for report in reports),
    }
    manual = [review for report in reports for review in report.get("manual_review", [])]
    if manual:
        counts = Counter(review["classification"] for review in manual)
        summary["manual_review"] = {"reviewed_additional_finding_count": len(manual), "classification_counts": dict(sorted(counts.items()))}
    summary["accepted"] = baseline_is_acceptable(reports)
    return summary


def build_eval_output(
    reports: list[dict[str, Any]],
    *,
    model: str,
    reasoning: str,
    backend: str,
    output_limit_metadata: dict[str, Any],
    complete: bool,
) -> dict[str, Any]:
    return {
        "eval_version": f"document-eval-{PROMPT_VERSION}",
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
        "input_contract_version": INPUT_CONTRACT_VERSION,
        "deterministic_observations_version": DETERMINISTIC_OBSERVATIONS_VERSION,
        "model": model,
        "reasoning": reasoning,
        **output_limit_metadata,
        "backend": backend,
        "complete": complete,
        "summary": summarize(reports),
        "cases": reports,
    }


def rescore_report(report: dict[str, Any], manifest: dict[str, Any], manifest_path: Path, reviews: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases_by_id = {case["id"]: case for case in manifest["cases"]}
    for case_report in report["cases"]:
        case = cases_by_id[case_report["case_id"]]
        case_input = load_case_input(case, manifest_path)
        materialized, errors = validate_and_materialize_result(
            dematerialize_code_owned_excerpts(
                case_report["result"], case_input.pages
            ),
            case_input.pages,
        )
        case_report["result"] = materialized
        case_report["validation_errors"] = errors
        case_report["metrics"] = score(case, case_report["result"], case_input.pages)
    if reviews is not None:
        attach_manual_review(report, reviews)
    report["summary"] = summarize(report["cases"])
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--backend", choices=["codex", "responses"], required=True)
    run.add_argument("--model", default="gpt-5.6-luna")
    run.add_argument("--reasoning", choices=["low", "medium", "high"], default="medium")
    run.add_argument("--max-output-tokens", type=int)
    run.add_argument("--confirm-live-model-run", action="store_true")
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--input-usd-per-million", type=float)
    run.add_argument("--output-usd-per-million", type=float)
    rescore = sub.add_parser("rescore")
    rescore.add_argument("--manifest", type=Path, required=True)
    rescore.add_argument("--input", type=Path, required=True)
    rescore.add_argument("--output", type=Path, required=True)
    rescore.add_argument("--manual-review", type=Path)
    args = parser.parse_args()

    manifest_path = require_private_path(args.manifest, "manifest")
    manifest = load_json(manifest_path)
    validate_manifest_limits(manifest)
    if args.command == "rescore":
        input_path = require_private_path(args.input, "rescore input")
        reviews = parse_manual_review(args.manual_review) if args.manual_review else None
        report = rescore_report(load_json(input_path), manifest, manifest_path, reviews)
        write_private_json(args.output, report)
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
        return 0 if report["summary"]["accepted"] else 1

    schema = load_json(SCHEMA_PATH)
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    output_limit_metadata = backend_output_limit_metadata(
        args.backend,
        args.max_output_tokens,
    )
    if not args.confirm_live_model_run:
        raise ValueError(
            "live eval requires --confirm-live-model-run after coordinator approval"
        )
    reports = []
    for case_index, case in enumerate(manifest["cases"], start=1):
        print(
            f"[{case_index}/{len(manifest['cases'])}] starting {case['id']}",
            file=sys.stderr,
            flush=True,
        )
        case_input = load_case_input(case, manifest_path)
        request_prompt = f"{instructions}\n\n{case_input.request_text}"
        started = time.perf_counter()
        if args.backend == "responses":
            result, usage, response_model = call_responses(
                args.model,
                args.reasoning,
                instructions,
                case_input.request_text,
                schema,
                output_limit_metadata["max_output_tokens"],
            )
        else:
            result, usage = call_codex(args.model, args.reasoning, request_prompt, SCHEMA_PATH)
            response_model = args.model
        latency = time.perf_counter() - started
        result, validation_errors = validate_and_materialize_result(
            result, case_input.pages
        )
        metrics = score(case, result, case_input.pages)
        input_tokens = token_value(usage, "input_tokens", "input_token_count")
        output_tokens = token_value(usage, "output_tokens", "output_token_count")
        estimated_cost = None
        if input_tokens is not None and output_tokens is not None and args.input_usd_per_million is not None and args.output_usd_per_million is not None:
            estimated_cost = input_tokens * args.input_usd_per_million / 1_000_000 + output_tokens * args.output_usd_per_million / 1_000_000
        reports.append({"case_id": case["id"], "response_model": response_model, "latency_seconds": latency, "usage": usage, "estimated_cost_usd": estimated_cost, "validation_errors": validation_errors, "metrics": metrics, "result": result})
        write_private_json(
            args.output,
            build_eval_output(
                reports,
                model=args.model,
                reasoning=args.reasoning,
                backend=args.backend,
                output_limit_metadata=output_limit_metadata,
                complete=False,
            ),
        )
        print(
            f"[{case_index}/{len(manifest['cases'])}] completed {case['id']} "
            f"in {latency:.2f}s",
            file=sys.stderr,
            flush=True,
        )

    output = build_eval_output(
        reports,
        model=args.model,
        reasoning=args.reasoning,
        backend=args.backend,
        output_limit_metadata=output_limit_metadata,
        complete=True,
    )
    summary = output["summary"]
    write_private_json(args.output, output)
    print(json.dumps(summary, indent=2))
    return 0 if summary["accepted"] else 1


if __name__ == "__main__":
    sys.exit(main())
