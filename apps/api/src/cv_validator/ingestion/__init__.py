from __future__ import annotations

from dataclasses import dataclass, field


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
class RedactedDocumentIdentity:
    algorithm: str
    format_version: str
    digest: str


@dataclass(frozen=True, init=False)
class _PageDocument:
    """Shared canonical page storage for raw and redacted documents."""

    pages: tuple[SourcePage, ...]
    source_format: str

    def __init__(
        self,
        *,
        pages: tuple[SourcePage, ...],
        source_format: str,
    ) -> None:
        canonical_pages = tuple(pages)
        page_ids = [page.page_id for page in canonical_pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page IDs must be unique within a document")
        object.__setattr__(self, "pages", canonical_pages)
        object.__setattr__(self, "source_format", source_format)

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
    ) -> None:
        super().__init__(pages=pages, source_format=source_format)
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
