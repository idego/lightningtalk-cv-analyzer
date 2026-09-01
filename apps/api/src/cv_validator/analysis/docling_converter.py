from __future__ import annotations

from io import BytesIO
from typing import Any

from docling.backend.abstract_backend import DeclarativeDocumentBackend
from docling.backend.docling_parse_backend import DoclingParseDocumentBackend
from docling.datamodel.base_models import DocumentStream, InputFormat
from docling.document_converter import DocumentConverter, FormatOption, WordFormatOption
from docling.pipeline.simple_pipeline import SimplePipeline
from docling_core.types.doc import DocItemLabel, DoclingDocument, ProvenanceItem

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
                cells = sorted(
                    page.get_text_cells(),
                    key=lambda cell: (
                        round(cell.rect.to_bounding_box().t, 3),
                        round(cell.rect.to_bounding_box().l, 3),
                    ),
                )
                for cell in cells:
                    text = cell.text.strip()
                    if not text:
                        continue
                    document.add_text(
                        label=DocItemLabel.TEXT,
                        text=text,
                        prov=ProvenanceItem(
                            page_no=page_number,
                            bbox=cell.rect.to_bounding_box(),
                            charspan=(0, len(text)),
                        ),
                    )
            finally:
                page.unload()
        return document

    def unload(self) -> None:
        self._pdf.unload()
        super().unload()


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


def _project(document: DoclingDocument, source_format: str) -> SourceDocument:
    blocks: list[SourceBlock] = []
    order = 0
    for item, _level in document.iterate_items(with_groups=True):
        item_id = _reference(item.self_ref)
        if item_id is None:
            continue
        parent_id = _reference(getattr(item, "parent", None))
        label = getattr(item, "label", None)
        kind = getattr(label, "value", None) or item.__class__.__name__.casefold()
        prov = tuple(getattr(item, "prov", ()) or ())
        page_number = prov[0].page_no if prov else None
        bbox = _bbox(prov[0].bbox) if prov else None
        text = str(getattr(item, "text", "") or "").strip()
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
