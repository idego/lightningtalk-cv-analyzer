from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceBlock:
    id: str
    text: str
    kind: str = "text"
    order: int = 0
    parent_id: str | None = None
    page_number: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    table_id: str | None = None
    row_index: int | None = None
    column_index: int | None = None

    def evidence(self, start: int, end: int) -> dict[str, object]:
        if start < 0 or end <= start or end > len(self.text):
            raise ValueError("evidence offsets are outside the source block")
        return {
            "source_id": self.id,
            "excerpt": self.text[start:end],
            "page_number": self.page_number,
            "start_offset": start,
            "end_offset": end,
        }


@dataclass(frozen=True)
class SourceDocument:
    blocks: tuple[SourceBlock, ...]
    source_format: str
    identity: str

    @classmethod
    def create(cls, blocks: tuple[SourceBlock, ...], source_format: str) -> "SourceDocument":
        canonical = [
            {
                "id": block.id,
                "text": block.text,
                "kind": block.kind,
                "order": block.order,
                "parent_id": block.parent_id,
                "page_number": block.page_number,
                "bbox": block.bbox,
                "table_id": block.table_id,
                "row_index": block.row_index,
                "column_index": block.column_index,
            }
            for block in blocks
        ]
        digest = hashlib.sha256(
            json.dumps(canonical, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return cls(blocks=blocks, source_format=source_format, identity=digest)

    def by_id(self) -> dict[str, SourceBlock]:
        return {block.id: block for block in self.blocks}

    def as_prompt_payload(self) -> list[dict[str, object]]:
        return [
            {
                "id": block.id,
                "text": block.text,
                "kind": block.kind,
                "order": block.order,
                "parent_id": block.parent_id,
                "page": block.page_number,
                "bbox": block.bbox,
                "table_id": block.table_id,
                "row": block.row_index,
                "column": block.column_index,
            }
            for block in self.blocks
        ]


TextSegment = SourceBlock
