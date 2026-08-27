from __future__ import annotations

import io
from collections.abc import Iterable

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from cv_validator.config import IngestionConfig, load_ingestion_config
from cv_validator.file_links.extraction import (
    extract_docx_file_details,
    extract_docx_hyperlinks,
    merge_document_links,
)
from cv_validator.ingestion import IngestionError, RawDocument, SourcePage
from cv_validator.ingestion.text import validate_text_sufficiency


def extract_docx(
    content: bytes, config: IngestionConfig | None = None
) -> RawDocument:
    try:
        document = Document(io.BytesIO(content))
        page_texts = _extract_logical_pages(document.iter_inner_content())
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Failed to read DOCX: {exc}") from exc

    pages = tuple(
        SourcePage(
            page_id=f"page-{page_number:04d}",
            page_number=page_number,
            text=text,
        )
        for page_number, text in enumerate(page_texts, start=1)
    )
    parsed = RawDocument(
        pages=pages,
        source_format="docx",
        file_details=extract_docx_file_details(document),
        document_links=merge_document_links(
            pages,
            extract_docx_hyperlinks(document, pages),
            source_format="docx",
        ),
    )
    validate_text_sufficiency(parsed, config or load_ingestion_config())
    return parsed


def _extract_logical_pages(blocks: Iterable[Paragraph | Table]) -> list[str]:
    page_fragments: list[list[str]] = [[]]

    for block in blocks:
        _append_block(block, page_fragments)

    return [
        _remove_paragraph_terminator("".join(fragments))
        for fragments in page_fragments
    ]


def _append_block(
    block: Paragraph | Table,
    page_fragments: list[list[str]],
) -> None:
    if isinstance(block, Paragraph):
        _append_paragraph(block, page_fragments)
        return

    seen_cells: set[int] = set()
    for row in block.rows:
        for cell in row.cells:
            cell_key = id(cell._tc)
            if cell_key in seen_cells:
                continue
            seen_cells.add(cell_key)
            for cell_block in cell.iter_inner_content():
                _append_block(cell_block, page_fragments)


def _append_paragraph(
    paragraph: Paragraph,
    page_fragments: list[list[str]],
) -> None:
    if _has_page_break_before(paragraph) and page_fragments[-1]:
        page_fragments.append([])

    for node in paragraph._p.iter():
        if node.tag == qn("w:t"):
            page_fragments[-1].append(node.text or "")
        elif node.tag == qn("w:tab"):
            page_fragments[-1].append("\t")
        elif node.tag == qn("w:br"):
            if node.get(qn("w:type")) == "page":
                page_fragments.append([])
            else:
                page_fragments[-1].append("\n")
        elif node.tag == qn("w:cr"):
            page_fragments[-1].append("\n")

    page_fragments[-1].append("\n")


def _has_page_break_before(paragraph: Paragraph) -> bool:
    properties = paragraph._p.pPr
    if properties is None:
        return False
    page_break = properties.find(qn("w:pageBreakBefore"))
    if page_break is None:
        return False
    return page_break.get(qn("w:val"), "true").lower() not in {
        "0",
        "false",
        "off",
    }


def _remove_paragraph_terminator(text: str) -> str:
    return text[:-1] if text.endswith("\n") else text
