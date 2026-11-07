"""PDF to Excel: every table found in the PDF becomes rows in a worksheet, one sheet per page."""

from __future__ import annotations

import re
from pathlib import Path

from file_converter.converters.base import EXCEL, ConversionError, Converter, ProgressCallback
from file_converter.converters.pdf_common import SCANNED_MESSAGE, inspect_pdf

# Fallback for PDFs whose tables have no ruling lines: line up columns by text position.
TEXT_TABLE_SETTINGS = {"vertical_strategy": "text", "horizontal_strategy": "text"}

_NUMBER = re.compile(r"^\(?-?[$€£₹]?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?\)?$|^\(?-?[$€£₹]?\s?\d+(?:\.\d+)?\)?$")


def to_cell_value(text: str | None):
    """Turn numeric-looking text into numbers so Excel can sum it; leave everything else as text."""
    if text is None:
        return None
    value = " ".join(text.split())
    if not value:
        return None
    if _NUMBER.match(value):
        negative = value.startswith("(") and value.endswith(")") or value.lstrip("(").startswith("-")
        digits = re.sub(r"[^\d.]", "", value)
        if digits and digits != ".":
            number = float(digits) if "." in digits else int(digits)
            if isinstance(number, int) and len(digits) > 1 and digits.startswith("0"):
                return value  # keep leading zeros (IDs, account numbers)
            return -number if negative else number
    return value


def extract_page_tables(page) -> list[list[list]]:
    tables = page.extract_tables()
    if not any(len(t) > 1 for t in tables):
        tables = page.extract_tables(TEXT_TABLE_SETTINGS)
    return [t for t in tables if t and any(any(c for c in row) for row in t)]


class PdfToExcel(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = EXCEL

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options=None) -> None:
        info = inspect_pdf(source)
        if not info.has_text:
            raise ConversionError(SCANNED_MESSAGE)

        import pdfplumber
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter

        workbook = Workbook()
        workbook.remove(workbook.active)
        found_any = False
        try:
            with pdfplumber.open(source) as pdf:
                total = len(pdf.pages)
                for index, page in enumerate(pdf.pages, start=1):
                    tables = extract_page_tables(page)
                    if tables:
                        found_any = True
                        sheet = workbook.create_sheet(f"Page {index}")
                        row_num = 1
                        for table in tables:
                            for r, row in enumerate(table):
                                for c, cell in enumerate(row, start=1):
                                    xl = sheet.cell(row=row_num, column=c, value=to_cell_value(cell))
                                    if r == 0:
                                        xl.font = Font(bold=True)
                                row_num += 1
                            row_num += 1  # blank row between tables
                        for col_cells in sheet.columns:
                            width = max((len(str(c.value)) for c in col_cells if c.value is not None), default=8)
                            sheet.column_dimensions[get_column_letter(col_cells[0].column)].width = min(width + 2, 60)
                    progress(0.9 * index / total)
        except ConversionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ConversionError(f"Couldn't read tables from this PDF: {exc}") from exc

        if not found_any:
            raise ConversionError("No tables were found in this PDF. Try converting it to Word instead.")
        workbook.save(destination)
        progress(1.0)
