from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE

from cv_validator.domain import (
    ComponentVersion,
    DocumentLink,
    Evidence,
    FileDetail,
    FileDetailField,
    FileDetailStatus,
    FileDetails,
    LinkAssociation,
    LinkRole,
    LinkSource,
)
from cv_validator.file_links.normalization import URLNormalizationError, normalize_url
from cv_validator.ingestion import SourcePage


PDF_METADATA_EXTRACTOR_VERSION = ComponentVersion("pdf-standard-metadata", "1")
DOCX_METADATA_EXTRACTOR_VERSION = ComponentVersion("docx-core-properties", "1")
PDF_HYPERLINK_EXTRACTOR_VERSION = ComponentVersion("pdf-uri-annotations", "1")
DOCX_HYPERLINK_EXTRACTOR_VERSION = ComponentVersion("docx-external-hyperlinks", "1")

_VISIBLE_URL = re.compile(r"(?i)(?<![\w])(?:https?://|www\.)[^\s<>]+")
_TRAILING_URL_PUNCTUATION = ".,;:!?\"'”’]}"
_PDF_METADATA_FIELDS = (
    FileDetailField.AUTHOR,
    FileDetailField.CREATOR,
    FileDetailField.PRODUCER,
    FileDetailField.TITLE,
    FileDetailField.SUBJECT,
    FileDetailField.CREATION_TIME,
    FileDetailField.MODIFICATION_TIME,
)
_DOCX_METADATA_FIELDS = (
    FileDetailField.AUTHOR,
    FileDetailField.LAST_MODIFIER,
    FileDetailField.CREATED,
    FileDetailField.MODIFIED,
    FileDetailField.REVISION,
    FileDetailField.TITLE,
    FileDetailField.SUBJECT,
)
_DOCX_DEFAULT_CREATED = "2013-12-23T23:15:00+00:00"


def extract_pdf_file_details(pdf: Any) -> FileDetails:
    metadata = getattr(pdf, "metadata", None) or {}
    values = {
        FileDetailField.AUTHOR: _metadata_text(metadata, "/Author", "Author"),
        FileDetailField.CREATOR: _metadata_text(metadata, "/Creator", "Creator"),
        FileDetailField.PRODUCER: _metadata_text(metadata, "/Producer", "Producer"),
        FileDetailField.TITLE: _metadata_text(metadata, "/Title", "Title"),
        FileDetailField.SUBJECT: _metadata_text(metadata, "/Subject", "Subject"),
        FileDetailField.CREATION_TIME: _pdf_date(
            _metadata_text(metadata, "/CreationDate", "CreationDate")
        ),
        FileDetailField.MODIFICATION_TIME: _pdf_date(
            _metadata_text(metadata, "/ModDate", "ModDate")
        ),
    }
    return _file_details(
        source_format="pdf",
        extractor_version=PDF_METADATA_EXTRACTOR_VERSION,
        fields=_PDF_METADATA_FIELDS,
        values=values,
    )


def extract_docx_file_details(document: Any) -> FileDetails:
    properties = _docx_core_properties(document)
    values = {
        FileDetailField.AUTHOR: _docx_property_text(properties, "author"),
        FileDetailField.LAST_MODIFIER: _object_text(properties, "last_modified_by"),
        FileDetailField.CREATED: _datetime_text(_object_value(properties, "created")),
        FileDetailField.MODIFIED: _datetime_text(_object_value(properties, "modified")),
        FileDetailField.REVISION: _docx_property_text(properties, "revision"),
        FileDetailField.TITLE: _object_text(properties, "title"),
        FileDetailField.SUBJECT: _object_text(properties, "subject"),
    }
    if values[FileDetailField.CREATED] == _DOCX_DEFAULT_CREATED:
        values[FileDetailField.CREATED] = None
    if values[FileDetailField.MODIFIED] == _DOCX_DEFAULT_CREATED:
        values[FileDetailField.MODIFIED] = None
    if (
        _object_value(properties, "revision") in {1, "1"}
        and values[FileDetailField.CREATED] is None
        and values[FileDetailField.MODIFIED] is None
        and values[FileDetailField.AUTHOR] is None
    ):
        values[FileDetailField.REVISION] = None
    return _file_details(
        source_format="docx",
        extractor_version=DOCX_METADATA_EXTRACTOR_VERSION,
        fields=_DOCX_METADATA_FIELDS,
        values=values,
    )


def extract_pdf_hyperlinks(
    pdf: Any,
    pages: tuple[SourcePage, ...],
) -> tuple[DocumentLink, ...]:
    links: list[DocumentLink] = []
    for index, (pdf_page, source_page) in enumerate(zip(pdf.pages, pages), start=1):
        try:
            annotations = tuple(getattr(pdf_page, "annots", None) or ())
        except Exception:  # noqa: BLE001
            annotations = ()
        for annotation_index, annotation in enumerate(annotations, start=1):
            target, invalid_reason = _pdf_annotation_target(annotation)
            displayed_value, evidence = _pdf_display_association(
                pdf_page,
                source_page,
                target,
            )
            links.append(
                DocumentLink(
                    id=f"link:pdf:page-{index:04d}:{annotation_index:04d}",
                    displayed_value=displayed_value,
                    target=target,
                    source_format="pdf",
                    source=LinkSource.EMBEDDED_HYPERLINK,
                    association=LinkAssociation.EMBEDDED_ONLY,
                    role=classify_link_role(displayed_value, source_page.text),
                    page_number=index,
                    evidence=evidence,
                    source_location="body",
                    invalid_reason=invalid_reason,
                )
            )
    return tuple(links)


def extract_docx_hyperlinks(
    document: Any,
    pages: tuple[SourcePage, ...],
    *,
    body_blocks: tuple[Any, ...] | None = None,
) -> tuple[DocumentLink, ...]:
    links: list[DocumentLink] = []
    link_index = 0
    current_page = 1

    for block in body_blocks if body_blocks is not None else document.iter_inner_content():
        for paragraph in _iter_paragraphs(block):
            paragraph_links, paragraph_end_page = _paragraph_hyperlinks_with_pages(
                paragraph,
                current_page,
            )
            for display, target, invalid_reason, link_page in paragraph_links:
                link_index += 1
                page = pages[link_page - 1] if pages else None
                evidence = _find_text_evidence(page, display) if page else ()
                links.append(
                    DocumentLink(
                        id=f"link:docx:body:{link_index:04d}",
                        displayed_value=display or None,
                        target=target,
                        source_format="docx",
                        source=LinkSource.EMBEDDED_HYPERLINK,
                        association=LinkAssociation.EMBEDDED_ONLY,
                        role=classify_link_role(display, page.text if page else ""),
                        page_number=link_page if page else None,
                        evidence=evidence,
                        source_location="body",
                        invalid_reason=invalid_reason,
                    )
                )
            current_page = min(paragraph_end_page, max(1, len(pages)))

    for section in getattr(document, "sections", ()):
        for location, container in (("header", section.header), ("footer", section.footer)):
            for block in _iter_container_blocks(container):
                for paragraph in _iter_paragraphs(block):
                    for display, target, invalid_reason in _paragraph_hyperlinks(paragraph):
                        link_index += 1
                        page = pages[0] if pages else None
                        links.append(
                            DocumentLink(
                                id=f"link:docx:{location}:{link_index:04d}",
                                displayed_value=display or None,
                                target=target,
                                source_format="docx",
                                source=LinkSource.EMBEDDED_HYPERLINK,
                                association=LinkAssociation.EMBEDDED_ONLY,
                                role=classify_link_role(display, ""),
                                page_number=page.page_number if page else None,
                                evidence=(),
                                source_location=location,
                                invalid_reason=invalid_reason,
                            )
                        )
    return tuple(links)


def merge_document_links(
    pages: tuple[SourcePage, ...],
    embedded_links: Iterable[DocumentLink],
    *,
    source_format: str,
) -> tuple[DocumentLink, ...]:
    visible_links = _visible_links(pages, source_format)
    remaining_visible = list(visible_links)
    merged: list[DocumentLink] = []
    seen_embedded: set[tuple[str | None, str | None, int | None, str]] = set()

    for embedded in embedded_links:
        key = (
            _comparison_key(embedded.target),
            embedded.displayed_value,
            embedded.page_number,
            embedded.source_location,
        )
        if key in seen_embedded:
            continue
        seen_embedded.add(key)
        match_index = _find_visible_match(embedded, remaining_visible)
        if match_index is None:
            merged.append(embedded)
            continue
        visible = remaining_visible.pop(match_index)
        mismatch = (
            _comparison_key(visible.displayed_value)
            and _comparison_key(embedded.target)
            and _comparison_key(visible.displayed_value)
            != _comparison_key(embedded.target)
        )
        merged.append(
            DocumentLink(
                id=visible.id,
                displayed_value=visible.displayed_value or embedded.displayed_value,
                target=embedded.target,
                source_format=source_format,
                source=LinkSource.VISIBLE_AND_EMBEDDED,
                association=(
                    LinkAssociation.MISMATCHED if mismatch else LinkAssociation.MATCHED
                ),
                role=(
                    embedded.role
                    if embedded.role is not LinkRole.GENERIC
                    else visible.role
                ),
                page_number=embedded.page_number or visible.page_number,
                evidence=visible.evidence or embedded.evidence,
                source_location=embedded.source_location,
                invalid_reason=embedded.invalid_reason,
            )
        )

    merged.extend(remaining_visible)
    return tuple(
        sorted(
            _deduplicate_links(merged),
            key=lambda link: (
                link.page_number or 0,
                link.evidence[0].start_offset if link.evidence else 10**9,
                link.id,
            ),
        )
    )


def classify_link_role(displayed_value: str | None, context: str) -> LinkRole:
    value = f"{displayed_value or ''} {context}".lower()
    if re.search(r"\b(profile|linkedin|resume|cv)\b", value):
        return LinkRole.PROFILE
    if re.search(r"\b(portfolio|behance|dribbble|design work)\b", value):
        return LinkRole.PORTFOLIO
    if re.search(r"\b(project|github|repository|repo|code)\b", value):
        return LinkRole.PROJECT
    if re.search(r"\b(publication|paper|research|article|doi)\b", value):
        return LinkRole.PUBLICATION
    if re.search(r"\b(credential|certificate|certification|license|licence)\b", value):
        return LinkRole.CREDENTIAL
    if re.search(r"\b(award|claim|proof|credential|qualification)\b", value):
        return LinkRole.CV_CLAIM
    return LinkRole.GENERIC


def _file_details(
    *,
    source_format: str,
    extractor_version: ComponentVersion,
    fields: tuple[FileDetailField, ...],
    values: dict[FileDetailField, str | None],
) -> FileDetails:
    return FileDetails(
        source_format=source_format,
        extractor_version=extractor_version,
        fields=tuple(
            FileDetail(
                field=field,
                value=values.get(field),
                status=(
                    FileDetailStatus.AVAILABLE
                    if values.get(field) is not None
                    else FileDetailStatus.UNAVAILABLE
                ),
                source_format=source_format,
                extractor_version=extractor_version,
            )
            for field in fields
        ),
    )


def _metadata_text(metadata: Any, *keys: str) -> str | None:
    for key in keys:
        value = metadata.get(key) if hasattr(metadata, "get") else None
        if value is not None:
            return _bounded_text(value)
    return None


def _object_value(value: Any, attribute: str) -> Any:
    if value is None:
        return None
    try:
        return getattr(value, attribute, None)
    except Exception:  # noqa: BLE001
        return None


def _docx_core_properties(document: Any) -> Any:
    package = _object_value(_object_value(document, "part"), "package")
    if package is None:
        return None
    try:
        core_part = package.part_related_by(RELATIONSHIP_TYPE.CORE_PROPERTIES)
    except (AttributeError, KeyError):
        return None
    return _object_value(core_part, "core_properties")


def _object_text(value: Any, attribute: str) -> str | None:
    raw = _object_value(value, attribute)
    if attribute == "revision" and raw in {0, "0"}:
        return None
    return _bounded_text(raw)


def _docx_property_text(value: Any, attribute: str) -> str | None:
    raw = _object_value(value, attribute)
    if attribute == "author" and isinstance(raw, str) and raw.strip().lower() == "python-docx":
        return None
    if attribute == "revision" and raw in {0, "0"}:
        return None
    return _bounded_text(raw)


def _bounded_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    text = " ".join(str(value).split()).strip()
    if any(ord(character) < 32 or ord(character) == 127 for character in text):
        return None
    return text[:1024] or None


def _datetime_text(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, datetime):
        return None
    return value.isoformat()


def _pdf_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.fullmatch(
        r"D:(?P<date>\d{4}(?:\d{2})?(?:\d{2})?)(?P<time>\d{2}\d{2}\d{2})?"
        r"(?P<zone>Z|[+-]\d{2}'?\d{2}'?)?",
        value.strip(),
    )
    if not match:
        return None
    date_part = match.group("date")
    if len(date_part) not in {4, 6, 8}:
        return None
    date_part += "01" * ((8 - len(date_part)) // 2)
    time_part = match.group("time") or "000000"
    zone = match.group("zone") or ""
    try:
        parsed = datetime.strptime(date_part + time_part, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    if zone == "Z":
        return parsed.isoformat() + "+00:00"
    if zone:
        compact_zone = zone.replace("'", "")
        sign = compact_zone[0]
        hours, minutes = compact_zone[1:3], compact_zone[3:5]
        if int(hours) > 23 or int(minutes) > 59:
            return None
        return f"{parsed.isoformat()}{sign}{hours}:{minutes}"
    return parsed.isoformat()


def _pdf_annotation_target(annotation: Any) -> tuple[str | None, str | None]:
    if not isinstance(annotation, dict):
        return None, "annotation_not_object"
    target = annotation.get("uri") or annotation.get("URI")
    if target is None:
        return None, "missing_uri"
    if isinstance(target, bytes):
        target = target.decode("utf-8", errors="replace")
    if not isinstance(target, str) or not target.strip():
        return None, "invalid_uri"
    return target.strip(), None


def _pdf_display_association(
    pdf_page: Any,
    source_page: SourcePage,
    target: str | None,
) -> tuple[str | None, tuple[Evidence, ...]]:
    """Use only text that can be found in the canonical page text as evidence."""
    visible_urls = _visible_links((source_page,), "pdf")
    if len(visible_urls) == 1:
        visible = visible_urls[0]
        if target and _comparison_key(visible.target) == _comparison_key(target):
            return visible.displayed_value, visible.evidence
        if target:
            return visible.displayed_value, visible.evidence
    return None, ()


def _visible_links(pages: tuple[SourcePage, ...], source_format: str) -> tuple[DocumentLink, ...]:
    links: list[DocumentLink] = []
    for page in pages:
        for index, match in enumerate(_VISIBLE_URL.finditer(page.text), start=1):
            displayed = _strip_url_punctuation(match.group(0))
            if not displayed:
                continue
            end_offset = match.start() + len(displayed)
            evidence = Evidence.from_page(page, match.start(), end_offset)
            links.append(
                DocumentLink(
                    id=f"link:{source_format}:visible:{page.page_id}:{match.start()}:{end_offset}",
                    displayed_value=displayed,
                    target=displayed,
                    source_format=source_format,
                    source=LinkSource.VISIBLE_URL,
                    association=LinkAssociation.VISIBLE_ONLY,
                    role=classify_link_role(displayed, _line_context(page.text, match.start())),
                    page_number=page.page_number,
                    evidence=(evidence,),
                    source_location="body",
                )
            )
    return tuple(links)


def _find_visible_match(
    embedded: DocumentLink,
    visible: list[DocumentLink],
) -> int | None:
    for index, candidate in enumerate(visible):
        if embedded.page_number != candidate.page_number:
            continue
        if embedded.displayed_value and _same_text(embedded.displayed_value, candidate.displayed_value):
            return index
        if _comparison_key(embedded.target) and _comparison_key(embedded.target) == _comparison_key(candidate.target):
            return index
    if embedded.source_format == "pdf" and embedded.displayed_value is None:
        same_page = [
            candidate for candidate in visible
            if candidate.page_number == embedded.page_number
        ]
        if len(same_page) == 1:
            return visible.index(same_page[0])
    return None


def _deduplicate_links(links: Iterable[DocumentLink]) -> tuple[DocumentLink, ...]:
    result: list[DocumentLink] = []
    keys: set[tuple[str | None, str | None, int | None, str]] = set()
    for link in links:
        key = (
            _comparison_key(link.target),
            link.displayed_value,
            link.page_number,
            link.source_location,
        )
        if link.target is None:
            key = (link.id, link.displayed_value, link.page_number, link.source_location)
        if key in keys:
            continue
        keys.add(key)
        result.append(link)
    return tuple(result)


def _comparison_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return normalize_url(value).comparison_key
    except URLNormalizationError:
        return None


def _same_text(left: str | None, right: str | None) -> bool:
    return bool(left and right and " ".join(left.split()).casefold() == " ".join(right.split()).casefold())


def _find_text_evidence(page: SourcePage | None, display: str | None) -> tuple[Evidence, ...]:
    if page is None or not display:
        return ()
    start = page.text.find(display)
    if start < 0:
        return ()
    return (Evidence.from_page(page, start, start + len(display)),)


def _line_context(text: str, offset: int) -> str:
    start = text.rfind("\n", 0, offset) + 1
    end = text.find("\n", offset)
    return text[start:] if end < 0 else text[start:end]


def _strip_url_punctuation(value: str) -> str:
    result = value
    while result and result[-1] in _TRAILING_URL_PUNCTUATION:
        result = result[:-1]
    while result.endswith(")") and result.count("(") < result.count(")"):
        result = result[:-1]
    return result


def _iter_paragraphs(block: Any) -> Iterable[Any]:
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    if isinstance(block, Paragraph):
        yield block
        return
    if isinstance(block, Table):
        seen_cells: set[int] = set()
        for row in block.rows:
            for cell in row.cells:
                cell_key = id(cell._tc)
                if cell_key in seen_cells:
                    continue
                seen_cells.add(cell_key)
                for cell_block in cell.iter_inner_content():
                    yield from _iter_paragraphs(cell_block)


def _iter_container_blocks(container: Any) -> Iterable[Any]:
    iterator = getattr(container, "iter_inner_content", None)
    if callable(iterator):
        yield from iterator()
        return
    for paragraph in getattr(container, "paragraphs", ()):
        yield paragraph
    for table in getattr(container, "tables", ()):
        yield table


def _paragraph_text(paragraph: Any) -> str:
    return "".join(node.text or "" for node in paragraph._p.iter() if _is_text_node(node))


def _is_text_node(node: Any) -> bool:
    from docx.oxml.ns import qn

    return node.tag in {qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")}


def _paragraph_starts_new_page(paragraph: Any) -> bool:
    from docx.oxml.ns import qn

    properties = paragraph._p.pPr
    if properties is not None:
        page_break = properties.find(qn("w:pageBreakBefore"))
        if page_break is not None and page_break.get(qn("w:val"), "true").lower() not in {"0", "false", "off"}:
            return True
    return any(
        node.tag == qn("w:br") and node.get(qn("w:type")) == "page"
        for node in paragraph._p.iter()
    )


def _paragraph_hyperlinks(paragraph: Any) -> Iterable[tuple[str, str | None, str | None]]:
    links, _ = _paragraph_hyperlinks_with_pages(paragraph, 1)
    for display, target, invalid_reason, _ in links:
        yield display, target, invalid_reason


def _paragraph_hyperlinks_with_pages(
    paragraph: Any,
    page_number: int,
) -> tuple[tuple[tuple[str, str | None, str | None, int], ...], int]:
    from docx.oxml.ns import qn

    current_page = page_number
    if _paragraph_has_page_break_before(paragraph):
        current_page += 1
    links: list[tuple[str, str | None, str | None, int]] = []
    for node in paragraph._p.iter():
        if node.tag == qn("w:br") and node.get(qn("w:type")) == "page":
            current_page += 1
            continue
        if node.tag != qn("w:hyperlink"):
            continue
        hyperlink = node
        display = "".join(
            node.text or "" for node in hyperlink.iter() if node.tag == qn("w:t")
        ).strip()
        relationship_id = hyperlink.get(qn("r:id"))
        if not relationship_id:
            links.append((display, None, "missing_relationship", current_page))
            continue
        try:
            relationship = paragraph.part.rels.get(relationship_id)
            target = getattr(relationship, "target_ref", None) if relationship else None
            external = getattr(relationship, "is_external", False) if relationship else False
        except Exception:  # noqa: BLE001
            relationship = None
            target = None
            external = False
        if relationship is None:
            links.append((display, None, "missing_relationship", current_page))
        elif not external or not target:
            links.append((display, None, "non_external_target", current_page))
        else:
            links.append((display, str(target), None, current_page))
    return tuple(links), current_page


def _paragraph_has_page_break_before(paragraph: Any) -> bool:
    from docx.oxml.ns import qn

    properties = paragraph._p.pPr
    if properties is None:
        return False
    page_break = properties.find(qn("w:pageBreakBefore"))
    return page_break is not None and page_break.get(qn("w:val"), "true").lower() not in {
        "0",
        "false",
        "off",
    }
