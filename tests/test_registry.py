from pathlib import Path

from file_converter.converters import EXCEL, WORD, Converter, ConverterRegistry, output_path_for


class FakePdfToWord(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = WORD

    def convert(self, source, destination, progress):
        destination.write_text("ok")


def test_find_matches_extension_and_format():
    registry = ConverterRegistry()
    conv = FakePdfToWord()
    registry.register(conv)
    assert registry.find(Path("a.PDF"), WORD) is conv
    assert registry.find(Path("a.pdf"), EXCEL) is None
    assert registry.find(Path("a.png"), WORD) is None


def test_output_path_never_overwrites(tmp_path):
    src = tmp_path / "report.pdf"
    src.write_text("x")
    first = output_path_for(src, WORD)
    assert first == tmp_path / "report.docx"
    first.write_text("existing")
    assert output_path_for(src, WORD) == tmp_path / "report (1).docx"


def test_output_path_uses_chosen_folder(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    assert output_path_for(tmp_path / "a.pdf", EXCEL, out) == out / "a.xlsx"
