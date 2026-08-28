from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from cv_validator.document_understanding.domain import Confidence, UnderstandingEvidence, stable_source_id
from cv_validator.document_understanding.normalization import normalize_text

DEFAULT_INDEX = Path(__file__).with_name("data") / "esco-skills-v1.json"
AMBIGUOUS_SHORT = {"c", "r", "go"}


@dataclass(frozen=True)
class SkillMatch:
    id: str
    canonical_id: str
    display_label: str
    taxonomy_version: str
    confidence: Confidence
    evidence: tuple[UnderstandingEvidence, ...]
    source_order: int


class SkillIndexError(ValueError):
    pass


def load_skill_index(path: Path = DEFAULT_INDEX) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = payload["manifest"]
        aliases = payload["aliases"]
        if manifest["build_version"] != "esco-index-v1" or not isinstance(aliases, list):
            raise SkillIndexError("incompatible ESCO skill index")
        canonical = json.dumps(aliases, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(canonical).hexdigest() != manifest["output_checksum"]:
            raise SkillIndexError("ESCO skill index checksum mismatch")
        for item in aliases:
            if set(item) != {"alias", "canonical_id", "display_label", "language"}:
                raise SkillIndexError("invalid ESCO alias record")
        return payload
    except (KeyError, OSError, TypeError, json.JSONDecodeError) as exc:
        raise SkillIndexError("unavailable ESCO skill index") from exc


def match_explicit_skills(document, sections, exclusion, *, index_path: Path = DEFAULT_INDEX):
    index = load_skill_index(index_path)
    aliases: dict[str, list[dict]] = {}
    for item in index["aliases"]:
        aliases.setdefault(normalize_text(item["alias"]), []).append(item)
    line_by_id = {line.line_id: line for line in document.source_lines}
    line_order = {line.line_id: order for order, line in enumerate(document.source_lines)}
    matches: dict[str, SkillMatch] = {}
    for section in sections:
        if section.kind.value != "skills":
            continue
        start, end = line_order[section.start_line_id], line_order[section.end_line_id]
        for line in document.source_lines[start + 1:end + 1]:
            normalized = normalize_text(line.text)
            for alias, entries in aliases.items():
                pattern = rf"(?<![\w]){re.escape(alias)}(?![\w])"
                if not re.search(pattern, normalized):
                    continue
                for entry in entries:
                    literal = _literal_match(line.text, entry["alias"])
                    if literal is None:
                        continue
                    begin, finish = literal
                    if exclusion.intersects(line.page_id, line.start_offset + begin, line.start_offset + finish):
                        continue
                    page = next(page for page in document.pages if page.page_id == line.page_id)
                    evidence = UnderstandingEvidence(line.page_id, page.page_number, line.line_id, line.start_offset + begin, line.start_offset + finish, "exact", line.text[begin:finish])
                    current = matches.get(entry["canonical_id"])
                    if current is None:
                        source_order = line_order[line.line_id] * 1_000_000 + begin
                        matches[entry["canonical_id"]] = SkillMatch(stable_source_id("skill", line.page_id, evidence.start_offset or 0, evidence.end_offset or 0), entry["canonical_id"], entry["display_label"], index["manifest"]["source_version"], Confidence.HIGH, (evidence,), source_order)
                    elif len(current.evidence) < 4 and evidence not in current.evidence:
                        matches[entry["canonical_id"]] = SkillMatch(current.id, current.canonical_id, current.display_label, current.taxonomy_version, current.confidence, (*current.evidence, evidence), current.source_order)
    return tuple(sorted(matches.values(), key=lambda item: (item.source_order, item.id)))


def _literal_match(text: str, alias: str) -> tuple[int, int] | None:
    match = re.search(rf"(?<![\w]){re.escape(alias)}(?![\w])", text, re.IGNORECASE)
    return match.span() if match else None
