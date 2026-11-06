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
