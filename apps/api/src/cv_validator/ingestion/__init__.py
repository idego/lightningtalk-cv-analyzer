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
    """Shared canonical page storage for raw and redacted documents.

    ``lines``, ``contact_region``, and ``body_region`` are temporary Slice 1
    compatibility views. New code must consume ``pages`` or ``source_lines``.

    The legacy four-argument constructor remains available during Slice 1 so
    existing deterministic consumers and tests can migrate separately.
    """

    pages: tuple[SourcePage, ...]
    source_format: str

    def __init__(
        self,
        lines: tuple[str, ...] | None = None,
        contact_region: tuple[str, ...] | None = None,
        body_region: tuple[str, ...] | None = None,
        source_format: str | None = None,
        *,
        pages: tuple[SourcePage, ...] | None = None,
    ) -> None:
        if source_format is None:
            raise TypeError("source_format is required")
        if pages is not None:
            if lines is not None or contact_region is not None or body_region is not None:
                raise TypeError("pages cannot be combined with legacy compatibility inputs")
            canonical_pages = tuple(pages)
        else:
            if lines is None:
                raise TypeError("pages or legacy lines are required")
            # contact_region and body_region are accepted only for constructor
            # compatibility. The views below are always derived from pages.
            canonical_pages = (
                SourcePage(
                    page_id="page-0001",
                    page_number=1,
                    text="\n".join(lines),
                ),
            )

        page_ids = [page.page_id for page in canonical_pages]
        if len(page_ids) != len(set(page_ids)):
            raise ValueError("page IDs must be unique within a document")
        object.__setattr__(self, "pages", canonical_pages)
        object.__setattr__(self, "source_format", source_format)

    @property
    def source_lines(self) -> tuple[SourceLine, ...]:
        return tuple(line for page in self.pages for line in page.lines)

    @property
    def lines(self) -> tuple[str, ...]:
        """Temporary normalized view for the Slice 1 deterministic adapter."""
        return tuple(
            line.text.strip() for line in self.source_lines if line.text.strip()
        )

    def _compatibility_regions(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        from cv_validator.ingestion.regions import split_contact_and_body

        contact, body = split_contact_and_body(list(self.lines))
        return tuple(contact), tuple(body)

    @property
    def contact_region(self) -> tuple[str, ...]:
        """Temporary Slice 1 compatibility view; do not use in new code."""
        return self._compatibility_regions()[0]

    @property
    def body_region(self) -> tuple[str, ...]:
        """Temporary Slice 1 compatibility view; do not use in new code."""
        return self._compatibility_regions()[1]

    @property
    def text(self) -> str:
        return "\n".join(self.lines)

    @property
    def contact_text(self) -> str:
        return "\n".join(self.contact_region)

    @property
    def body_text(self) -> str:
        return "\n".join(self.body_region)


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


# Temporary constructor/import compatibility for Slice 1 tests and consumers.
# The ingestion boundary itself now returns RawDocument explicitly.
ParsedCV = RawDocument
