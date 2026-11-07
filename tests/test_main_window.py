import time
from pathlib import Path

from PySide6.QtCore import QThreadPool

from file_converter.converters import WORD, ConversionError, Converter, ConverterRegistry
from file_converter.ui.main_window import MainWindow


class FakeConverter(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = WORD

    def convert(self, source, destination, progress, options=None):
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
    w.select_action(WORD)
    w.convert_all()
    wait_until(qapp, lambda: not w._jobs)

    statuses = {e.path.name: e.status for e in w.entries}
    assert statuses["good.pdf"] == "Done"
    assert statuses["bad.pdf"] == "Failed"
    assert statuses["scan.png"] == "Not supported yet"
    assert (tmp_path / "good.docx").read_text() == "converted"
    assert not (tmp_path / "bad.docx").exists()
    assert w.convert_button.isEnabled()


# ---- the real toolkit in the window -----------------------------------------

from pdf_samples import numbered_pdf, page_texts  # noqa: E402

from file_converter.converters import default_registry  # noqa: E402
from file_converter.converters.pdf_pages import MERGE, ROTATE  # noqa: E402
from file_converter.converters.pdf_security import PROTECT  # noqa: E402


def real_window(qapp):
    return MainWindow(default_registry(), QThreadPool())


def test_tool_list_has_group_headers_and_options(qapp):
    w = real_window(qapp)
    labels = [w.action_combo.itemText(i).strip() for i in range(w.action_combo.count())]
    assert "ORGANIZE PAGES" in labels and "Merge PDFs into one" in labels
    assert w.current_action() == WORD
    assert w.options_box.isHidden()
    w.select_action(ROTATE)
    assert not w.options_box.isHidden()
    assert w.option_values() == {"angle": 90, "pages": ""}


def test_merge_in_list_order_after_moving(qapp, tmp_path):
    w = real_window(qapp)
    a = numbered_pdf(tmp_path / "a.pdf", 1)
    b = numbered_pdf(tmp_path / "b.pdf", 2)
    w.add_files([a, b])
    w.table.selectRow(1)
    w.move_selected(-1)
    assert [e.path.name for e in w.entries] == ["b.pdf", "a.pdf"]
    w.select_action(MERGE)
    w.convert_all()
    wait_until(qapp, lambda: not w._jobs)
    assert [e.status for e in w.entries] == ["Done", "Done"]
    merged = tmp_path / "b (merged).pdf"
    assert page_texts(merged) == ["Page 1", "Page 2", "Page 1"]
    assert w.entries[0].output == merged


def test_required_option_blocks_start_and_skips_wrong_files(qapp, tmp_path):
    w = real_window(qapp)
    pdf = numbered_pdf(tmp_path / "doc.pdf", 1)
    png = tmp_path / "pic.png"
    png.write_bytes(b"")
    w.add_files([pdf, png])
    w.select_action(PROTECT)
    w.convert_all()
    assert not w._jobs and w.entries[0].status == "Ready"
    w.set_option("password", "pw")
    w.convert_all()
    wait_until(qapp, lambda: not w._jobs)
    assert w.entries[0].status == "Done"
    assert w.entries[1].status == "Skipped"
    assert (tmp_path / "doc (protected).pdf").exists()

    # Picking another tool makes finished files ready to run again.
    w.select_action(ROTATE)
    assert [e.status for e in w.entries] == ["Ready", "Ready"]


def test_remove_selected(qapp, tmp_path):
    w = real_window(qapp)
    files = [numbered_pdf(tmp_path / f"{n}.pdf", 1) for n in "abc"]
    w.add_files(files)
    w.table.selectRow(1)
    w.remove_selected()
    assert [e.path.name for e in w.entries] == ["a.pdf", "c.pdf"]
    assert w.table.rowCount() == 2


# ---- drag and drop ----------------------------------------------------------

from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402


def _mime(paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


def _drop_target(widget: QWidget) -> QWidget | None:
    """The widget Qt delivers a drop to: the first one up the parent chain
    that accepts drops."""
    while widget is not None and not widget.acceptDrops():
        widget = widget.parentWidget()
    return widget


def test_drops_anywhere_on_window_reach_the_window(qapp):
    w = make_window(qapp)
    for child in (w.drop_area, w.table.viewport(), w.convert_button, w.action_combo):
        assert _drop_target(child) is w


def test_drop_adds_files_and_folders(qapp, tmp_path):
    w = make_window(qapp)
    pdf = tmp_path / "a.pdf"
    pdf.write_text("x")
    folder = tmp_path / "more"
    folder.mkdir()
    (folder / "b.pdf").write_text("x")
    (folder / "notes.txt").write_text("x")
    mime = _mime([pdf, folder])
    actions = Qt.DropAction.CopyAction
    enter = QDragEnterEvent(QPoint(10, 10), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, enter)
    assert enter.isAccepted()
    drop = QDropEvent(QPointF(10, 10), actions, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, drop)
    assert drop.isAccepted()
    assert [e.path.name for e in w.entries] == ["a.pdf", "b.pdf"]


def test_drag_without_files_is_refused(qapp):
    w = make_window(qapp)
    mime = QMimeData()
    mime.setText("hello")
    enter = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(w, enter)
    assert not enter.isAccepted()
