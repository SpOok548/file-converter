import time
from pathlib import Path

from PySide6.QtCore import QThreadPool

from file_converter.converters import WORD, ConversionError, Converter, ConverterRegistry
from file_converter.ui.main_window import MainWindow


class FakeConverter(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = WORD

    def convert(self, source, destination, progress):
        if "bad" in source.name:
            raise ConversionError("This PDF is password protected")
        progress(0.5)
        destination.write_text("converted")
        progress(1.0)


def wait_until(qapp, condition, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if condition():
            return
        time.sleep(0.01)
    raise AssertionError("timed out")


def make_window(qapp):
    registry = ConverterRegistry()
    registry.register(FakeConverter())
    return MainWindow(registry, QThreadPool())


def test_add_files_filters_unsupported_and_duplicates(qapp, tmp_path):
    w = make_window(qapp)
    pdf = tmp_path / "a.pdf"
    pdf.write_text("x")
    w.add_files([pdf, tmp_path / "notes.txt", pdf])
    assert [e.path for e in w.entries] == [pdf]
    assert w.convert_button.isEnabled()


def test_convert_success_and_failure(qapp, tmp_path):
    w = make_window(qapp)
    good, bad, img = tmp_path / "good.pdf", tmp_path / "bad.pdf", tmp_path / "scan.png"
    for p in (good, bad, img):
        p.write_text("x")
    w.add_files([good, bad, img])
    w.format_combo.setCurrentIndex(w.format_combo.findData(WORD))
    w.convert_all()
    wait_until(qapp, lambda: not w._jobs)

    statuses = {e.path.name: e.status for e in w.entries}
    assert statuses["good.pdf"] == "Done"
    assert statuses["bad.pdf"] == "Failed"
    assert statuses["scan.png"] == "Not supported yet"
    assert (tmp_path / "good.docx").read_text() == "converted"
    assert not (tmp_path / "bad.docx").exists()
    assert w.convert_button.isEnabled()
