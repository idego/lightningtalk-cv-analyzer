from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import urlsplit

import phonenumbers

from cv_validator.analysis.source import TextSegment


MECHANICAL_VERSION = "mechanical-extraction-v1"

_EMAIL_RE = re.compile(r"(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})(?![\w.-])", re.I)
_URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>\"']+")
_PHONE_RE = re.compile(r"(?<!\w)(?:\+|00)\d[\d\s().-]{6,}\d(?!\w)")
_POSTAL_PATTERNS = {
    "PL": re.compile(r"\b\d{2}-\d{3}\b"),
    "GB": re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.I),
    "DE": re.compile(r"\b\d{5}\b"),
    "FR": re.compile(r"\b\d{5}\b"),
    "US": re.compile(r"\b\d{5}(?:-\d{4})?\b"),
}
_COMMON_EMAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "live.com",
    "yahoo.com",
    "proton.me",
    "protonmail.com",
    "icloud.com",
    "onet.pl",
    "op.pl",
    "wp.pl",
    "o2.pl",
    "interia.pl",
}


def extract_mechanical(segments: Iterable[TextSegment]) -> dict[str, object]:
    materialized = tuple(segments)
    emails = _extract_emails(materialized)
    return {
        "phones": _extract_phones(materialized),
        "emails": emails,
        "literal_links": _extract_links(materialized),
        "postal_candidates": _extract_postal_candidates(materialized),
        "accepted_postal_addresses": [],
        "email_findings": _email_findings(emails),
        "location_resolution": [],
        "eu_status": None,
    }


def _extract_emails(segments: tuple[TextSegment, ...]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for segment in segments:
        for match in _EMAIL_RE.finditer(segment.text):
            value = match.group(1)
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            found.append({"value": value, "evidence": [segment.evidence(*match.span(1))]})
    return found


def _extract_links(segments: tuple[TextSegment, ...]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for segment in segments:
        for match in _URL_RE.finditer(segment.text):
            literal = match.group(0).rstrip(".,;:!?)").strip()
            normalized = literal if literal.casefold().startswith(("http://", "https://")) else f"https://{literal}"
            host = (urlsplit(normalized).hostname or "").casefold()
            key = normalized.casefold()
            if not host or key in seen:
                continue
            seen.add(key)
            known_host = None
            if host in {"linkedin.com", "www.linkedin.com"}:
                known_host = "linkedin"
            elif host in {"github.com", "www.github.com"}:
                known_host = "github"
            found.append(
                {
                    "value": literal,
                    "normalized_url": normalized,
                    "known_host": known_host,
                    "evidence": [segment.evidence(match.start(), match.start() + len(literal))],
                }
            )
    return found


def _extract_phones(segments: tuple[TextSegment, ...]) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for segment in segments:
        for match in _PHONE_RE.finditer(segment.text):
            literal = match.group(0).strip()
            parse_value = f"+{literal[2:]}" if literal.startswith("00") else literal
            normalized = re.sub(r"[^\d+]", "", parse_value)
            if normalized in seen:
                continue
            seen.add(normalized)
            country_code = None
            status = "unresolved"
            try:
                parsed = phonenumbers.parse(parse_value, None)
                if phonenumbers.is_valid_number(parsed):
                    region = phonenumbers.region_code_for_number(parsed)
                    country_code = region if region and region != "001" else None
                    status = "resolved" if country_code else "ambiguous"
                elif phonenumbers.is_possible_number(parsed):
                    status = "possible"
                else:
                    status = "invalid"
            except phonenumbers.NumberParseException:
                status = "invalid"
            found.append(
                {
                    "value": literal,
                    "normalized": normalized,
                    "country_code": country_code,
                    "status": status,
                    "evidence": [segment.evidence(*match.span())],
                }
            )
    return found


def _extract_postal_candidates(segments: tuple[TextSegment, ...]) -> list[dict[str, object]]:
    by_location: dict[tuple[str, int, int], dict[str, object]] = {}
    for segment in segments:
        for country_code, pattern in _POSTAL_PATTERNS.items():
            for match in pattern.finditer(segment.text):
                key = (segment.id, match.start(), match.end())
                candidate = by_location.setdefault(
                    key,
                    {
                        "value": match.group(0),
                        "possible_country_codes": [],
                        "ownership_status": "candidate",
                        "evidence": [segment.evidence(*match.span())],
                    },
                )
                candidate["possible_country_codes"].append(country_code)
    return list(by_location.values())


def _email_findings(emails: list[dict[str, object]]) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for email in emails:
        value = str(email["value"])
        domain = value.rsplit("@", 1)[-1].casefold()
        if domain in _COMMON_EMAIL_DOMAINS or domain.count(".") != 1:
            continue
        matches = [
            known
            for known in _COMMON_EMAIL_DOMAINS
            if _edit_distance_at_most_one(domain, known) == 1
        ]
        if len(matches) == 1:
            findings.append(
                {
                    "kind": "possible_common_provider_typo",
                    "observed_domain": domain,
                    "suggested_domain": matches[0],
                    "evidence": email["evidence"],
                }
            )
    return findings


def _edit_distance_at_most_one(left: str, right: str) -> int:
    if left == right:
        return 0
    if abs(len(left) - len(right)) > 1:
        return 2
    if len(left) > len(right):
        left, right = right, left
    if len(left) == len(right):
        differences = sum(a != b for a, b in zip(left, right))
        if differences <= 1:
            return differences
        for index in range(len(left) - 1):
            if left[index] == right[index + 1] and left[index + 1] == right[index]:
                if left[:index] == right[:index] and left[index + 2 :] == right[index + 2 :]:
                    return 1
        return 2
    left_index = right_index = differences = 0
    while left_index < len(left) and right_index < len(right):
        if left[left_index] == right[right_index]:
            left_index += 1
            right_index += 1
            continue
        differences += 1
        right_index += 1
        if differences > 1:
            return 2
    return 1
