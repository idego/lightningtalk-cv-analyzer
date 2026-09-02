from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any

from docling.backend.abstract_backend import DeclarativeDocumentBackend
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.document_converter import DocumentConverter, FormatOption, WordFormatOption
from docling.pipeline.simple_pipeline import SimplePipeline
from docling_core.types.doc import BoundingBox, DocItemLabel, DoclingDocument, GroupLabel, ProvenanceItem

from cv_validator.analysis.source import SourceBlock, SourceDocument
from cv_validator.analysis.strategy import AnalysisStrategyError, SourceFormat


DOCLING_VERSION = "2.124.0"
CONVERTER_VERSION = "docling-text-only-v1"
MIN_USEFUL_TEXT_CHARACTERS = 20


class TextOnlyPdfBackend(DeclarativeDocumentBackend):
    """Build a DoclingDocument from a PDF's native text layer only."""

    def __init__(self, in_doc, path_or_stream, options=None) -> None:
        super().__init__(in_doc, path_or_stream, options)
        source = (
            BytesIO(path_or_stream.getvalue())
            if isinstance(path_or_stream, BytesIO)
            else path_or_stream
        )
        self._pdf = DoclingParseDocumentBackend(in_doc, source)

    @classmethod
    def supported_formats(cls) -> set[InputFormat]:
        return {InputFormat.PDF}

    @classmethod
    def supports_pagination(cls) -> bool:
        return False

    def is_valid(self) -> bool:
        return self._pdf.is_valid()

    def convert(self) -> DoclingDocument:
        document = DoclingDocument(name=self.file.stem or "document")
        for page_index in range(self._pdf.page_count()):
            page = self._pdf.load_page(
                page_index,
                create_words=False,
                create_textlines=True,
            )
            try:
                size = page.get_size()
                page_number = page_index + 1
                document.add_page(page_no=page_number, size=size)
                lines = sorted(
                    (
                        _Line(cell.text.strip(), cell.rect.to_bounding_box())
                        for cell in page.get_text_cells()
                        if cell.text.strip()
                    ),
                    key=lambda line: (round(line.bbox.t, 3), round(line.bbox.l, 3)),
                )
                for paragraph in _merge_wrapped_lines(lines):
                    document.add_text(
                        label=DocItemLabel.TEXT,
                        text=paragraph.text,
                        prov=ProvenanceItem(
                            page_no=page_number,
                            bbox=paragraph.bbox,
                            charspan=(0, len(paragraph.text)),
                        ),
                    )
            finally:
                page.unload()
        return document

    def unload(self) -> None:
        self._pdf.unload()
        super().unload()


@dataclass(frozen=True)
class _Line:
    text: str
    bbox: BoundingBox
    last_line: BoundingBox | None = None

    @property
    def tail(self) -> BoundingBox:
        """Bounding box of the most recent physical line (for paragraphs, the last one)."""
        return self.last_line or self.bbox

    @property
    def height(self) -> float:
        return abs(float(self.tail.b) - float(self.tail.t))


# A continuation line sits below the previous one by less than this share of the
# line height; separate entries in CVs are typically spaced by a full line or more.
MAX_WRAP_GAP_RATIO = 0.6
MAX_HEIGHT_DRIFT_RATIO = 0.1
MAX_INDENT_DRIFT_POINTS = 24.0
BULLET_PREFIXES = ("●", "•", "◦", "○", "▪", "▫", "■", "‣", "-", "–", "—", "*", "·")


def _merge_wrapped_lines(lines: list[_Line]) -> list[_Line]:
    paragraphs: list[_Line] = []
    for line in lines:
        if paragraphs and _continues(paragraphs[-1], line):
            previous = paragraphs[-1]
            paragraphs[-1] = _Line(
                text=f"{previous.text} {line.text}",
                bbox=BoundingBox(
                    l=min(previous.bbox.l, line.bbox.l),
                    t=min(previous.bbox.t, line.bbox.t),
                    r=max(previous.bbox.r, line.bbox.r),
                    b=max(previous.bbox.b, line.bbox.b),
                    coord_origin=previous.bbox.coord_origin,
                ),
                last_line=line.bbox,
            )
        else:
            paragraphs.append(line)
    return paragraphs


def _continues(previous: _Line, current: _Line) -> bool:
    """Whether `current` is the wrapped continuation of `previous` (same paragraph)."""
    if current.text.startswith(BULLET_PREFIXES):
        return False
    reference = max(previous.height, current.height)
    if reference <= 0:
        return False
    if abs(previous.height - current.height) > MAX_HEIGHT_DRIFT_RATIO * reference:
        return False
    gap = float(current.bbox.t) - float(previous.tail.b)
    if gap < -0.5 * reference or gap > MAX_WRAP_GAP_RATIO * reference:
        return False
    # Guard multi-column layouts: the lines must share horizontal extent.
    if float(current.bbox.l) >= float(previous.tail.r) or float(current.bbox.r) <= float(previous.tail.l):
        return False
    indent = float(current.bbox.l) - float(previous.tail.l)
    return -MAX_INDENT_DRIFT_POINTS <= indent <= MAX_INDENT_DRIFT_POINTS


class DoclingTextConverter:
    def __init__(self) -> None:
        self._converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
            format_options={
                InputFormat.PDF: FormatOption(
                    pipeline_cls=SimplePipeline,
                    backend=TextOnlyPdfBackend,
                ),
                InputFormat.DOCX: WordFormatOption(),
            },
        )

    def convert(
        self,
        content: bytes,
        filename: str,
        source_format: SourceFormat,
    ) -> SourceDocument:
        try:
            result = self._converter.convert(
                DocumentStream(name=filename, stream=BytesIO(content)),
                raises_on_error=True,
            )
            source = _project(result.document, source_format.value)
        except AnalysisStrategyError:
            raise
        except Exception as exc:
            raise AnalysisStrategyError("document_conversion_failed") from exc
        useful = sum(len(block.text.strip()) for block in source.blocks)
        if useful < MIN_USEFUL_TEXT_CHARACTERS:
            raise AnalysisStrategyError("document_text_layer_unavailable")
        return source


NO_SPACE_BEFORE = (",", ".", ";", ":", ")", "!", "?")


def _project(document: DoclingDocument, source_format: str) -> SourceDocument:
    blocks: list[SourceBlock] = []
    inline_groups: set[str] = set()
    order = 0
    for item, _level in document.iterate_items(with_groups=True):
        item_id = _reference(item.self_ref)
        if item_id is None:
            continue
        parent_id = _reference(getattr(item, "parent", None))
        label = getattr(item, "label", None)
        if label == GroupLabel.INLINE:
            inline_groups.add(item_id)
            continue
        kind = getattr(label, "value", None) or item.__class__.__name__.casefold()
        prov = tuple(getattr(item, "prov", ()) or ())
        page_number = prov[0].page_no if prov else None
        bbox = _bbox(prov[0].bbox) if prov else None
        text = str(getattr(item, "text", "") or "").strip()
        if text and blocks and _is_inline_continuation(blocks[-1], parent_id, kind, inline_groups):
            previous = blocks[-1]
            joiner = "" if text.startswith(NO_SPACE_BEFORE) or previous.text.endswith("(") else " "
            blocks[-1] = SourceBlock(
                id=previous.id,
                text=f"{previous.text}{joiner}{text}",
                kind=previous.kind,
                order=previous.order,
                parent_id=previous.parent_id,
                page_number=previous.page_number,
                bbox=previous.bbox,
            )
            continue
        if text:
            blocks.append(
                SourceBlock(
                    id=item_id,
                    text=text,
                    kind=kind,
                    order=order,
                    parent_id=parent_id,
                    page_number=page_number,
                    bbox=bbox,
                )
            )
            order += 1
        data = getattr(item, "data", None)
        for cell in getattr(data, "table_cells", ()) or ():
            cell_text = str(cell.text or "").strip()
            if not cell_text:
                continue
            row = int(cell.start_row_offset_idx)
            column = int(cell.start_col_offset_idx)
            blocks.append(
                SourceBlock(
                    id=f"{item_id}/cell-{row}-{column}",
                    text=cell_text,
                    kind="table_cell",
                    order=order,
                    parent_id=item_id,
                    page_number=page_number,
                    bbox=_bbox(cell.bbox) if cell.bbox is not None else bbox,
                    table_id=item_id,
                    row_index=row,
                    column_index=column,
                )
            )
            order += 1
    return SourceDocument.create(tuple(blocks), source_format)


def _is_inline_continuation(
    previous: SourceBlock,
    parent_id: str | None,
    kind: str,
    inline_groups: set[str],
) -> bool:
    """Formatted runs of one DOCX paragraph arrive as separate text items under an
    inline group; they are one paragraph and must form one evidence block."""
    return (
        parent_id is not None
        and parent_id in inline_groups
        and previous.parent_id == parent_id
        and previous.table_id is None
        and kind == "text"
        and previous.kind == "text"
    )


def _reference(value: Any) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "cref", value)
    return str(raw).removeprefix("#/")


def _bbox(value: Any) -> tuple[float, float, float, float]:
    return tuple(
        round(float(getattr(value, name)), 3)
        for name in ("l", "t", "r", "b")
    )
