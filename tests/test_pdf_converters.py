import pytest
from docx import Document
from openpyxl import load_workbook

from file_converter.converters import EXCEL, WORD, ConversionError, default_registry
from file_converter.converters.pdf_to_excel import PdfToExcel, to_cell_value
from file_converter.converters.pdf_to_word import PdfToWord
from pdf_samples import password_pdf, ruled_table_pdf, scanned_pdf, text_only_pdf


def run(converter, source, dest):
    seen = []
    converter.convert(source, dest, seen.append)
    assert seen and seen[-1] == 1.0
    assert all(0.0 <= p <= 1.0 for p in seen)
    return seen


def test_registry_has_pdf_converters(tmp_path):
    reg = default_registry()
    assert isinstance(reg.find(tmp_path / "a.pdf", WORD), PdfToWord)
    assert isinstance(reg.find(tmp_path / "a.pdf", EXCEL), PdfToExcel)


def test_pdf_to_word_keeps_text_and_table(tmp_path):
    out = tmp_path / "invoice.docx"
    run(PdfToWord(), ruled_table_pdf(tmp_path / "invoice.pdf"), out)
    doc = Document(out)
    text = "\n".join(p.text for p in doc.paragraphs)
    cells = [c.text for t in doc.tables for row in t.rows for c in row.cells]
    assert "Invoice 0042" in text
    assert "Thank you for your business." in text
    assert "Stapler" in cells + text.split()


def test_pdf_to_excel_extracts_table_with_numbers(tmp_path):
    out = tmp_path / "invoice.xlsx"
    run(PdfToExcel(), ruled_table_pdf(tmp_path / "invoice.pdf"), out)
    wb = load_workbook(out)
    assert wb.sheetnames == ["Page 1"]  # page 2 has no table
    rows = [[c for c in row if c is not None] for row in wb["Page 1"].iter_rows(values_only=True)]
    rows = [r for r in rows if r]
    assert rows[0] == ["Item", "Qty", "Price"]
    assert rows[1] == ["Paper", 2, 4.5]
    assert rows[2] == ["Ink", 1, 1250.0]
    assert rows[3] == ["Stapler", 3, -12.0]


def test_pdf_to_excel_without_tables_explains(tmp_path):
    with pytest.raises(ConversionError, match="No tables"):
        PdfToExcel().convert(text_only_pdf(tmp_path / "letter.pdf"), tmp_path / "x.xlsx", lambda p: None)


@pytest.mark.parametrize("converter", [PdfToWord(), PdfToExcel()])
def test_scanned_pdf_explains(tmp_path, converter):
    with pytest.raises(ConversionError, match="scan"):
        converter.convert(scanned_pdf(tmp_path / "scan.pdf"), tmp_path / "x.out", lambda p: None)


@pytest.mark.parametrize("converter", [PdfToWord(), PdfToExcel()])
def test_password_pdf_explains(tmp_path, converter):
    with pytest.raises(ConversionError, match="password"):
        converter.convert(password_pdf(tmp_path / "locked.pdf"), tmp_path / "x.out", lambda p: None)


@pytest.mark.parametrize("converter", [PdfToWord(), PdfToExcel()])
def test_damaged_pdf_explains(tmp_path, converter):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ConversionError, match="damaged"):
        converter.convert(bad, tmp_path / "x.out", lambda p: None)


@pytest.mark.parametrize(
    "text, expected",
    [
        ("42", 42),
        ("1,234.50", 1234.5),
        ("(12.00)", -12.0),
        ("-3", -3),
        ("$ 5.25", 5.25),
        ("00123", "00123"),
        ("2024-01-05", "2024-01-05"),
        ("  Total  due ", "Total due"),
        ("", None),
        (None, None),
    ],
)
def test_to_cell_value(text, expected):
    assert to_cell_value(text) == expected
