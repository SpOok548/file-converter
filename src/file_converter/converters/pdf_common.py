"""Checks shared by the PDF converters, so users get a clear message up front."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from file_converter.converters.base import ConversionError

SCANNED_MESSAGE = (
    "This PDF has no selectable text, so it looks like a scan. "
    "Support for scanned PDFs (text recognition) is coming in a later version."
)


@dataclass(frozen=True)
class PdfInfo:
    page_count: int
    has_text: bool


def inspect_pdf(source: Path) -> PdfInfo:
    import pymupdf

    try:
        doc = pymupdf.open(source)
    except Exception as exc:  # noqa: BLE001 - PyMuPDF raises several types for bad files
        raise ConversionError("This file couldn't be opened as a PDF. It may be damaged.") from exc
    with doc:
        if doc.needs_pass:
            raise ConversionError("This PDF is password protected. Remove the password and try again.")
        if doc.page_count == 0:
            raise ConversionError("This PDF has no pages.")
        has_text = any(page.get_text("text").strip() for page in doc)
        return PdfInfo(page_count=doc.page_count, has_text=has_text)


def open_pdf(source: Path, password: str | None = None):
    """Open a PDF for editing, turning library errors into messages a user can act on."""
    import pymupdf

    try:
        doc = pymupdf.open(source)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError("This file couldn't be opened as a PDF. It may be damaged.") from exc
    if not doc.is_pdf:
        doc.close()
        raise ConversionError("This file isn't a PDF.")
    if doc.needs_pass:
        if password is None:
            doc.close()
            raise ConversionError(
                "This PDF is password protected. Use the \"Remove password\" tool first."
            )
        if not doc.authenticate(password):
            doc.close()
            raise ConversionError("That password is wrong for this PDF.")
    if doc.page_count == 0:
        doc.close()
        raise ConversionError("This PDF has no pages.")
    return doc


def save_pdf(doc, destination: Path, **kwargs) -> None:
    """Save compactly; every tool writes a new file and never touches the original."""
    try:
        doc.save(destination, garbage=3, deflate=True, **kwargs)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Couldn't save the new PDF: {exc}") from exc


def parse_pages(text: str | None, page_count: int) -> list[int]:
    """Turn "1-3, 5, 8-" into zero-based page indexes. Blank means every page.

    Pages are kept in the order typed, without repeats, so "3, 1-2" gives pages 3, 1, 2.
    """
    if not text or not text.strip():
        return list(range(page_count))
    pages: list[int] = []
    for part in text.replace(";", ",").split(","):
        part = part.strip().lower()
        if not part:
            continue
        try:
            if "-" in part:
                start_text, end_text = (p.strip() for p in part.split("-", 1))
                start = int(start_text) if start_text else 1
                end = page_count if end_text in ("", "end") else int(end_text)
            else:
                start = end = page_count if part == "end" else int(part)
        except ValueError:
            raise ConversionError(f'"{part}" isn\'t a page number or range. Use something like 1-3, 5, 8-.') from None
        if start < 1 or end < start:
            raise ConversionError(f'"{part}" isn\'t a valid page range.')
        if start > page_count:
            raise ConversionError(f"This PDF has only {page_count} page(s), so \"{part}\" is out of range.")
        for number in range(start, min(end, page_count) + 1):
            if number - 1 not in pages:
                pages.append(number - 1)
    if not pages:
        raise ConversionError("No pages were selected.")
    return pages


def page_groups(text: str | None, page_count: int) -> list[list[int]]:
    """Split instructions: blank means one file per page, otherwise one file per comma-separated part."""
    if not text or not text.strip():
        return [[i] for i in range(page_count)]
    return [parse_pages(part, page_count) for part in text.replace(";", ",").split(",") if part.strip()]


def describe_pages(indexes: list[int]) -> str:
    """[0, 1, 2] -> "1-3", used in split file names."""
    first, last = indexes[0] + 1, indexes[-1] + 1
    if len(indexes) == 1:
        return f"{first}"
    if indexes == list(range(indexes[0], indexes[-1] + 1)):
        return f"{first}-{last}"
    return f"{first}-{last} selection"


def has_encryption(doc) -> bool:
    """True for PDFs with an open password and for PDFs with only a permissions password."""
    return bool(doc.needs_pass or doc.is_encrypted or (doc.metadata or {}).get("encryption"))
