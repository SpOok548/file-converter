from openpyxl import load_workbook

from file_converter.app import main
from pdf_samples import ruled_table_pdf, scanned_pdf


def test_cli_converts_to_excel(tmp_path, capsys):
    src = ruled_table_pdf(tmp_path / "inv.pdf")
    out = tmp_path / "out.xlsx"
    assert main(["prog", "--convert", str(src), "--to", "xlsx", "--output", str(out)]) == 0
    assert load_workbook(out).sheetnames == ["Page 1"]


def test_cli_reports_failure(tmp_path, capsys):
    src = scanned_pdf(tmp_path / "scan.pdf")
    assert main(["prog", "--convert", str(src), "--to", "docx"]) == 1
    assert "scan" in capsys.readouterr().err
