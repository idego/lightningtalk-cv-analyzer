from __future__ import annotations

from dataclasses import dataclass, field

from cv_validator.domain import DocumentLink, FileDetails


class IngestionError(Exception):
    """Raised when a CV cannot be ingested."""


class EmptyTextError(IngestionError):
    """Raised when extraction yields no meaningful document text."""


class InsufficientTextError(IngestionError):
    """Raised when extraction yields some text, but not enough to analyze."""


@dataclass(frozen=True)
class SourceLine:
    """One source line with offsets into its canonical page text."""

    page_id: str
    line_number: int
    text: str = field(repr=False)
    start_offset: int
    end_offset: int

    @property
    def line_id(self) -> str:
        return f"{self.page_id}-line-{self.line_number:04d}"


@dataclass(frozen=True)
class SourcePage:
    """A real PDF page or an explicitly delimited logical DOCX page."""

    page_id: str
    page_number: int
    text: str = field(repr=False)
    lines: tuple[SourceLine, ...] = field(init=False)

    def __post_init__(self) -> None:
        normalized_text = self.text.replace("\r\n", "\n").replace("\r", "\n")
        object.__setattr__(self, "text", normalized_text)

        source_lines: list[SourceLine] = []
        offset = 0
        for line_number, raw_line in enumerate(
            normalized_text.splitlines(keepends=True), start=1
        ):
            line_text = raw_line[:-1] if raw_line.endswith("\n") else raw_line
            source_lines.append(
                SourceLine(
                    page_id=self.page_id,
                    line_number=line_number,
                    text=line_text,
                    start_offset=offset,
                    end_offset=offset + len(line_text),
                )
            )
            offset += len(raw_line)
        object.__setattr__(self, "lines", tuple(source_lines))


@dataclass(frozen=True)
class NationalIdRedaction:
    page_id: str
    page_number: int
    start_offset: int
    end_offset: int
    type_hints: tuple[str, ...]


@dataclass(frozen=True)
class PresentationSpan:
    page_id: str
    page_number: int
    text: str = field(repr=False)
    start_offset: int | None = None
    end_offset: int | None = None
    paragraph_path: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    association: str = "unmapped"
    font_size_points: float | None = None
    bold: bool | None = None
    foreground_luminance: float | None = None
    background_luminance: float | None = None
    opacity: float | None = None
    explicit_hidden: bool = False
    redaction_type_hints: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceBlock:
    """Reusable source structure mapped to canonical page text."""
    id: str
    page_id: str
    page_number: int
    source_order: int
    kind: str
    line_ids: tuple[str, ...]
    start_offset: int | None
    end_offset: int | None
    paragraph_path: str | None = None
    table_id: str | None = None
    row_index: int | None = None
    list_level: int | None = None
    bbox: tuple[float, float, float, float] | None = None
    association: str = "exact"


@dataclass(frozen=True)
class RedactedDocumentIdentity:
    algorithm: str
    format_version: str
    digest: str


@dataclass(frozen=True, init=False)
class _PageDocument:
    """Shared canonical page storage for raw and redacted documents."""

    pages: tuple[SourcePage, ...]
    source_format: str
    file_details: FileDetails | None
    document_links: tuple[DocumentLink, ...]
    presentation_spans: tuple[PresentationSpan, ...]
    presentation_audited_parts: tuple[str, ...]
    presentation_omitted_parts: tuple[str, ...]
    presentation_truncated: bool
    source_blocks: tuple[SourceBlock, ...]
    source_blocks_partial: bool

    def __init__(
        self,
        *,
        pages: tuple[SourcePage, ...],
        source_format: str,
        file_details: FileDetails | None = None,
        document_links: tuple[DocumentLink, ...] = (),
        presentation_spans: tuple[PresentationSpan, ...] = (),
        presentation_audited_parts: tuple[str, ...] = (),
        presentation_omitted_parts: tuple[str, ...] = (),
        presentation_truncated: bool = False,
        source_blocks: tuple[SourceBlock, ...] | None = None,
        source_blocks_partial: bool = False,
    ) -> None:
        canonical_pages = tuple(pages)
        page_ids = [page.page_id for page in canonical_pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page IDs must be unique within a document")
        object.__setattr__(self, "pages", canonical_pages)
        object.__setattr__(self, "source_format", source_format)
        object.__setattr__(self, "file_details", file_details)
        object.__setattr__(self, "document_links", tuple(document_links))
        object.__setattr__(self, "presentation_spans", tuple(presentation_spans))
        object.__setattr__(self, "presentation_audited_parts", tuple(presentation_audited_parts))
        object.__setattr__(self, "presentation_omitted_parts", tuple(presentation_omitted_parts))
        object.__setattr__(self, "presentation_truncated", presentation_truncated)
        if source_blocks is None:
            generated: list[SourceBlock] = []
            for page in canonical_pages:
                for line in page.lines:
                    generated.append(SourceBlock(
                        id=f"source-block-{len(generated)+1:04d}",
                        page_id=page.page_id, page_number=page.page_number,
                        source_order=len(generated), kind="line",
                        line_ids=(line.line_id,), start_offset=line.start_offset,
                        end_offset=line.end_offset,
                    ))
            source_blocks = tuple(generated)
        object.__setattr__(self, "source_blocks", tuple(source_blocks))
        object.__setattr__(self, "source_blocks_partial", source_blocks_partial)

    @property
    def source_lines(self) -> tuple[SourceLine, ...]:
        return tuple(line for page in self.pages for line in page.lines)


class RawDocument(_PageDocument):
    """Canonical extracted source that may contain sensitive national IDs."""


@dataclass(frozen=True, init=False)
class RedactedDocument(_PageDocument):
    """Canonical source after mandatory national-ID masking."""

    redactions: tuple[NationalIdRedaction, ...]

    def __init__(
        self,
        *,
        pages: tuple[SourcePage, ...],
        source_format: str,
        redactions: tuple[NationalIdRedaction, ...] = (),
        file_details: FileDetails | None = None,
        document_links: tuple[DocumentLink, ...] = (),
        presentation_spans: tuple[PresentationSpan, ...] = (),
        presentation_audited_parts: tuple[str, ...] = (),
        presentation_omitted_parts: tuple[str, ...] = (),
        presentation_truncated: bool = False,
        source_blocks: tuple[SourceBlock, ...] | None = None,
        source_blocks_partial: bool = False,
    ) -> None:
        super().__init__(
            pages=pages,
            source_format=source_format,
            file_details=file_details,
            document_links=document_links,
            presentation_spans=presentation_spans,
            presentation_audited_parts=presentation_audited_parts,
            presentation_omitted_parts=presentation_omitted_parts,
            presentation_truncated=presentation_truncated,
            source_blocks=source_blocks,
            source_blocks_partial=source_blocks_partial,
        )
        object.__setattr__(self, "redactions", tuple(redactions))

    @property
    def markdown(self) -> str:
        from cv_validator.ingestion.text import to_page_markdown

        return to_page_markdown(self)

    @property
    def canonical_text(self) -> str:
        from cv_validator.ingestion.text import redacted_canonical_text

        return redacted_canonical_text(self)

    @property
    def identity(self) -> RedactedDocumentIdentity:
        from cv_validator.ingestion.text import redacted_document_identity

        return redacted_document_identity(self)
