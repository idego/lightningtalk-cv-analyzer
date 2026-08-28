from __future__ import annotations

import io

import pdfplumber

from cv_validator.config import IngestionConfig, load_ingestion_config
from cv_validator.file_links.extraction import (
    extract_pdf_file_details,
    extract_pdf_hyperlinks,
    merge_document_links,
)
from cv_validator.ingestion import IngestionError, PresentationSpan, RawDocument, SourceBlock, SourcePage
from cv_validator.structural.config import StructuralAuditConfig
from cv_validator.ingestion.text import validate_text_sufficiency


def extract_pdf(
    content: bytes, config: IngestionConfig | None = None
) -> RawDocument:
    try:
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = tuple(
                SourcePage(
                    page_id=f"page-{page_number:04d}",
                    page_number=page_number,
                    text=page.extract_text() or "",
                )
                for page_number, page in enumerate(pdf.pages, start=1)
            )
            file_details = extract_pdf_file_details(pdf)
            embedded_links = extract_pdf_hyperlinks(pdf, pages)
            try:
                presentation_spans, presentation_truncated = _presentation_spans(pdf.pages, pages)
                presentation_omitted = []
            except Exception:  # Presentation inspection must not break text ingestion.
                presentation_spans, presentation_truncated = (), False
                presentation_omitted = ["pdf_page_text_spans_unavailable"]
            omitted_parts = tuple(
                "pdf_non_text_content"
                for page in pdf.pages
                if page.images
            ) + tuple(presentation_omitted)
            source_blocks = _source_blocks(pages, presentation_spans)
    except Exception as exc:  # noqa: BLE001
        raise IngestionError(f"Failed to read PDF: {exc}") from exc

    parsed = RawDocument(
        pages=pages,
        source_format="pdf",
        file_details=file_details,
        document_links=merge_document_links(
            pages,
            embedded_links,
            source_format="pdf",
        ),
        presentation_spans=presentation_spans,
        presentation_audited_parts=("pdf_page_text_spans",),
        presentation_omitted_parts=omitted_parts,
        presentation_truncated=presentation_truncated,
        source_blocks=source_blocks,
        source_blocks_partial=any(block.association != "exact" for block in source_blocks),
    )
    validate_text_sufficiency(parsed, config or load_ingestion_config())
    return parsed


def _presentation_spans(pdf_pages, canonical_pages):
    cfg = StructuralAuditConfig()
    spans = []
    atom_count = 0
    truncated = False
    for pdf_page, canonical in zip(pdf_pages, canonical_pages):
        search_from = 0
        for char in pdf_page.chars:
            atom_count += 1
            if atom_count > cfg.max_pdf_atoms:
                truncated = True
                break
            text = str(char.get("text") or "")
            if not text:
                continue
            found = canonical.text.find(text, search_from)
            exact = found >= 0
            if exact:
                search_from = found + len(text)
            color = char.get("non_stroking_color")
            luminance = _luminance(color)
            opacity = char.get("non_stroking_alpha")
            partial_offset = None
            if not exact and len(text) > 1:
                partial_offset = canonical.text.find(text[:1], search_from)
            association = "exact" if exact else "partial" if partial_offset is not None and partial_offset >= 0 else "unmapped"
            start_offset = found if exact else partial_offset if association == "partial" else None
            end_offset = found + len(text) if exact else partial_offset + 1 if association == "partial" else None
            background = _known_background_luminance(pdf_page, char)
            spans.append(PresentationSpan(
                page_id=canonical.page_id, page_number=canonical.page_number, text=text,
                start_offset=start_offset, end_offset=end_offset,
                bbox=(float(char["x0"]), float(char["top"]), float(char["x1"]), float(char["bottom"])),
                association=association, font_size_points=float(char["size"]) if char.get("size") is not None else None,
                foreground_luminance=luminance, background_luminance=background, opacity=float(opacity) if opacity is not None else None,
            ))
        if truncated:
            break
    return tuple(spans), truncated


def _source_blocks(canonical_pages, presentation_spans):
    blocks=[]
    for canonical in canonical_pages:
        page_spans = [span for span in presentation_spans if span.page_id == canonical.page_id and span.bbox is not None]
        for line in canonical.lines:
            line_words=[span for span in page_spans if span.start_offset is not None and span.end_offset is not None and span.start_offset < line.end_offset and span.end_offset > line.start_offset]
            bbox=None
            if line_words:
                bbox=(min(w.bbox[0] for w in line_words), min(w.bbox[1] for w in line_words), max(w.bbox[2] for w in line_words), max(w.bbox[3] for w in line_words))
            blocks.append(SourceBlock(
                id=f"source-block-{len(blocks)+1:04d}", page_id=canonical.page_id,
                page_number=canonical.page_number, source_order=len(blocks), kind="line",
                line_ids=(line.line_id,), start_offset=line.start_offset, end_offset=line.end_offset,
                bbox=bbox, association="exact" if bbox is not None else "partial",
            ))
    return tuple(blocks)


def _luminance(color):
    if not isinstance(color, (tuple, list)) or len(color) != 3:
        return None
    values = [float(value) for value in color]
    if max(values) > 1:
        values = [value / 255 for value in values]
    return 0.2126 * values[0] + 0.7152 * values[1] + 0.0722 * values[2]


def _known_background_luminance(page, char):
    """Return luminance only for an explicit filled rectangle covering the glyph."""
    candidates = []
    for rect in page.rects:
        if not rect.get("fill"):
            continue
        if rect["x0"] <= char["x0"] and rect["x1"] >= char["x1"] and rect["top"] <= char["top"] and rect["bottom"] >= char["bottom"]:
            luminance = _luminance(rect.get("non_stroking_color"))
            if luminance is not None:
                candidates.append((float(rect["x1"] - rect["x0"]) * float(rect["bottom"] - rect["top"]), luminance))
    return min(candidates)[1] if candidates else None
