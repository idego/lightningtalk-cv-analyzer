from __future__ import annotations

import unicodedata
from typing import Any, Callable


def subject_key(category: str, subject: str) -> tuple[str, str]:
    normalized = unicodedata.normalize("NFKC", subject).casefold()
    return category, " ".join(normalized.split())


def derive_subject_union(stored_report: dict[str, Any], category: str, *, ai_category: str, limit: int, safe: Callable[[str], bool]) -> tuple[dict[str, str], ...]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    understanding = stored_report.get("document_understanding")
    if isinstance(understanding, dict):
        for item in understanding.get("code_research_subjects", []):
            if not isinstance(item, dict) or item.get("category") != category:
                continue
            subject = item.get("subject")
            if not isinstance(subject, str) or not safe(subject):
                continue
            key = subject_key(category, subject)
            if key in seen:
                continue
            seen.add(key); result.append({"subject": subject.strip(), "authority": "code", "record_id": str(item.get("record_id") or "")})
            if len(result) == limit:
                return tuple(result)
    ai = stored_report.get("ai_analysis") or {}
    candidates = ai.get("research_candidates") or []
    for item in candidates:
        if not isinstance(item, dict) or item.get("category") != ai_category:
            continue
        subject = item.get("query_subject")
        if not isinstance(subject, str) or not safe(subject):
            continue
        key = subject_key(category, subject)
        if key in seen:
            continue
        seen.add(key); result.append({"subject": subject.strip(), "authority": "ai"})
        if len(result) == limit:
            break
    return tuple(result)
