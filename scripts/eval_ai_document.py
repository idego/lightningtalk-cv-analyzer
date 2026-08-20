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
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_EVAL_ROOT = (ROOT / "data/ai-eval").resolve()
PROMPT_PATH = ROOT / "docs/ai-eval/prompt.md"
SCHEMA_PATH = ROOT / "docs/ai-eval/document-analysis.schema.json"
CHECK_IDS = {"contact", "education", "employment", "timeline", "duration_claims", "relationships", "document_quality", "protected_boundaries"}
MANUAL_LABELS = {"true positive", "przydatne „warto wiedzieć”", "duplikat", "nadinterpretacja", "artefakt parsowania/flatteningu"}


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


def iter_evidence(result: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    facts = result.get("facts")
    if isinstance(facts, dict):
        for group, items in facts.items():
            if isinstance(items, list):
                for index, item in enumerate(items):
                    if isinstance(item, dict) and isinstance(item.get("evidence"), list):
                        for evidence_index, evidence in enumerate(item["evidence"]):
                            if isinstance(evidence, dict):
                                yield f"facts.{group}[{index}].evidence[{evidence_index}]", evidence
    findings = result.get("findings")
    if isinstance(findings, list):
        for index, finding in enumerate(findings):
            if isinstance(finding, dict) and isinstance(finding.get("evidence"), list):
                for evidence_index, evidence in enumerate(finding["evidence"]):
                    if isinstance(evidence, dict):
                        yield f"findings[{index}].evidence[{evidence_index}]", evidence
    candidates = result.get("research_candidates")
    if isinstance(candidates, list):
        for index, candidate in enumerate(candidates):
            if isinstance(candidate, dict) and isinstance(candidate.get("evidence"), dict):
                yield f"research_candidates[{index}].evidence", candidate["evidence"]


def validate_result(result: dict[str, Any], source: str, schema: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    selected_schema = schema or load_json(SCHEMA_PATH)
    validator = Draft202012Validator(selected_schema)
    for validation_error in sorted(validator.iter_errors(result), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in validation_error.absolute_path) or "<root>"
        errors.append(f"schema {location}: {validation_error.message}")

    for location, evidence in iter_evidence(result):
        if evidence.get("page_id") != "p1" or evidence.get("excerpt", "") not in source:
            errors.append(f"{location}: evidence is not an exact excerpt from flattened input")

    checks = result.get("checklist")
    if isinstance(checks, list):
        check_ids = [item.get("id") for item in checks if isinstance(item, dict)]
        if set(check_ids) != CHECK_IDS or len(check_ids) != len(CHECK_IDS):
            errors.append("checklist must contain every required id exactly once")
    return errors


def response_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") in {"output_text", "text"} and content.get("text"):
                    return content["text"]
    raise ValueError("Responses API returned no output text")


def call_responses(model: str, reasoning: str, instructions: str, document: str, schema: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --backend responses")
    payload = {
        "model": model,
        "reasoning": {"effort": reasoning},
        "instructions": instructions,
        "input": [{"role": "user", "content": [{"type": "input_text", "text": document}]}],
        "text": {"format": {"type": "json_schema", "name": "document_analysis", "strict": True, "schema": schema}},
        "tools": [],
        "store": False,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as raw:
        response = json.load(raw)
    return json.loads(response_text(response)), response.get("usage", {})


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
    needle = expected.get("evidence_contains", "").casefold()
    excerpts = " ".join(item.get("excerpt", "") for item in finding.get("evidence", [])).casefold()
    return not needle or needle in excerpts


def score(case: dict[str, Any], result: dict[str, Any], source: str) -> dict[str, Any]:
    expected = case["expected_findings"]
    findings = result.get("findings", [])
    matched_expected = {index for index, item in enumerate(expected) if any(matches(item, finding) for finding in findings)}
    matched_findings = {index for index, finding in enumerate(findings) if any(matches(item, finding) for item in expected)}
    evidence_items = [evidence for finding in findings for evidence in finding.get("evidence", [])]
    accurate = sum(evidence.get("page_id") == "p1" and evidence.get("excerpt", "") in source for evidence in evidence_items)
    unsupported_findings = sum(
        not finding.get("evidence")
        or any(evidence.get("page_id") != "p1" or evidence.get("excerpt", "") not in source for evidence in finding.get("evidence", []))
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
        "unexpected_finding_count": len(findings) - len(matched_findings),
        "finding_evidence_item_count": len(evidence_items),
        "finding_evidence_exact_match_accuracy_flattened_input": accurate / len(evidence_items) if evidence_items else 1.0,
        "forbidden_output_hits": forbidden_hits,
    }


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
    summary: dict[str, Any] = {
        "case_count": len(reports),
        "valid_case_count": len(valid),
        "macro_recall": sum(report["metrics"]["recall"] for report in reports) / len(reports),
        "recall_is_not_precision": True,
        "unsupported_finding_count": sum(report["metrics"]["unsupported_finding_count"] for report in reports),
        "unexpected_finding_count": sum(report["metrics"]["unexpected_finding_count"] for report in reports),
        "finding_evidence_exact_match_accuracy_flattened_input": sum(report["metrics"]["finding_evidence_exact_match_accuracy_flattened_input"] for report in reports) / len(reports),
        "total_latency_seconds": sum(report["latency_seconds"] for report in reports),
        "estimated_cost_usd": None if any(report["estimated_cost_usd"] is None for report in reports) else sum(report["estimated_cost_usd"] for report in reports),
    }
    manual = [review for report in reports for review in report.get("manual_review", [])]
    if manual:
        counts = Counter(review["classification"] for review in manual)
        summary["manual_review"] = {"reviewed_additional_finding_count": len(manual), "classification_counts": dict(sorted(counts.items()))}
    return summary


def rescore_report(report: dict[str, Any], manifest: dict[str, Any], manifest_path: Path, reviews: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    cases_by_id = {case["id"]: case for case in manifest["cases"]}
    for case_report in report["cases"]:
        case = cases_by_id[case_report["case_id"]]
        source = (manifest_path.parent / case["input"]).read_text(encoding="utf-8")
        case_report["validation_errors"] = validate_result(case_report["result"], source)
        case_report["metrics"] = score(case, case_report["result"], source)
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
    if args.command == "rescore":
        input_path = require_private_path(args.input, "rescore input")
        reviews = parse_manual_review(args.manual_review) if args.manual_review else None
        report = rescore_report(load_json(input_path), manifest, manifest_path, reviews)
        write_private_json(args.output, report)
        print(json.dumps(report["summary"], indent=2, ensure_ascii=False))
        return 0 if report["summary"]["valid_case_count"] == report["summary"]["case_count"] else 1

    schema = load_json(SCHEMA_PATH)
    instructions = PROMPT_PATH.read_text(encoding="utf-8")
    reports = []
    for case in manifest["cases"]:
        source_path = manifest_path.parent / case["input"]
        source = source_path.read_text(encoding="utf-8")
        document = f"<document page_id=\"p1\">\n{source}\n</document>"
        request_prompt = f"{instructions}\n\n{document}"
        started = time.perf_counter()
        if args.backend == "responses":
            result, usage = call_responses(args.model, args.reasoning, instructions, document, schema)
        else:
            result, usage = call_codex(args.model, args.reasoning, request_prompt, SCHEMA_PATH)
        latency = time.perf_counter() - started
        validation_errors = validate_result(result, source, schema)
        metrics = score(case, result, source)
        input_tokens = token_value(usage, "input_tokens", "input_token_count")
        output_tokens = token_value(usage, "output_tokens", "output_token_count")
        estimated_cost = None
        if input_tokens is not None and output_tokens is not None and args.input_usd_per_million is not None and args.output_usd_per_million is not None:
            estimated_cost = input_tokens * args.input_usd_per_million / 1_000_000 + output_tokens * args.output_usd_per_million / 1_000_000
        reports.append({"case_id": case["id"], "latency_seconds": latency, "usage": usage, "estimated_cost_usd": estimated_cost, "validation_errors": validation_errors, "metrics": metrics, "result": result})

    summary = summarize(reports)
    output = {"eval_version": "document-eval-2008", "prompt_version": "2008", "schema_version": "document-analysis-schema-v2", "model": args.model, "reasoning": args.reasoning, "backend": args.backend, "summary": summary, "cases": reports}
    write_private_json(args.output, output)
    print(json.dumps(summary, indent=2))
    return 0 if summary["valid_case_count"] == summary["case_count"] and not any(report["metrics"]["forbidden_output_hits"] for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
