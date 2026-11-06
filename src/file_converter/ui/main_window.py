"""Main window: add files, choose a format, convert, see results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_converter.converters import (
    OUTPUT_FORMATS,
    SUPPORTED_INPUTS,
    ConverterRegistry,
    output_path_for,
)
from file_converter.worker import ConversionJob

COL_FILE, COL_STATUS, COL_PROGRESS = range(3)


@dataclass
class FileEntry:
    path: Path
    row: int
    status: str = "Ready"
    output: Path | None = None


class DropArea(QFrame):
    def __init__(self, on_files, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_files = on_files
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(110)
        self.setStyleSheet(
            "#dropArea { border: 2px dashed palette(mid); border-radius: 10px; }"
            "#dropArea[hover=\"true\"] { border-color: palette(highlight); }"
        )
        layout = QVBoxLayout(self)
        title = QLabel("Drop PDFs or images here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = title.font()
        font.setPointSizeF(font.pointSizeF() * 1.3)
        title.setFont(font)
        hint = QLabel("PDF, PNG, JPG, BMP, TIFF, WEBP")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setEnabled(False)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addStretch()

    def _set_hover(self, on: bool) -> None:
        self.setProperty("hover", on)
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._set_hover(True)

    def dragLeaveEvent(self, event) -> None:
        self._set_hover(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_hover(False)
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        self._on_files(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, registry: ConverterRegistry, pool: QThreadPool | None = None) -> None:
        super().__init__()
        self.registry = registry
        self.pool = pool or QThreadPool(self)
        self.pool.setMaxThreadCount(1)  # one conversion at a time keeps memory use predictable
        self.entries: list[FileEntry] = []
        self.output_dir: Path | None = None
        self._jobs: dict[int, ConversionJob] = {}

        self.setWindowTitle("File Converter")
        self.resize(760, 540)

        central = QWidget()
        root = QVBoxLayout(central)

        self.drop_area = DropArea(self.add_files)
        root.addWidget(self.drop_area)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["File", "Status", "Progress"])
        self.table.horizontalHeader().setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(COL_PROGRESS, 140)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self._open_result)
        self.table.currentCellChanged.connect(self._show_row_details)
        root.addWidget(self.table, 1)

        file_row = QHBoxLayout()
        self.add_button = QPushButton("Add files…")
        self.add_button.clicked.connect(self._browse_files)
        self.clear_button = QPushButton("Clear list")
        self.clear_button.clicked.connect(self.clear)
        file_row.addWidget(self.add_button)
        file_row.addWidget(self.clear_button)
        file_row.addStretch()
        root.addLayout(file_row)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Convert to:"))
        self.format_combo = QComboBox()
        for fmt in OUTPUT_FORMATS:
            self.format_combo.addItem(fmt.label, fmt)
        action_row.addWidget(self.format_combo)
        action_row.addSpacing(16)
        action_row.addWidget(QLabel("Save to:"))
        self.output_button = QPushButton("Same folder as original")
        self.output_button.clicked.connect(self._choose_output_dir)
        action_row.addWidget(self.output_button)
        action_row.addStretch()
        self.convert_button = QPushButton("Convert")
        self.convert_button.setDefault(True)
        self.convert_button.clicked.connect(self.convert_all)
        action_row.addWidget(self.convert_button)
        root.addLayout(action_row)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Add files to get started. Double-click a finished file to open it.")
        self._update_buttons()

    # ---- file list -------------------------------------------------------

    def add_files(self, paths: list[Path]) -> None:
        paths = list(paths)
        known = {e.path for e in self.entries}
        skipped = 0
        for path in paths:
            if path.is_dir():
                paths.extend(sorted(p for p in path.iterdir() if p.is_file()))
                continue
            if path.suffix.lower() not in SUPPORTED_INPUTS:
                skipped += 1
                continue
            if path in known:
                continue
            known.add(path)
            row = self.table.rowCount()
            self.table.insertRow(row)
            item = QTableWidgetItem(path.name)
            item.setToolTip(str(path))
            self.table.setItem(row, COL_FILE, item)
            self.table.setItem(row, COL_STATUS, QTableWidgetItem("Ready"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            self.table.setCellWidget(row, COL_PROGRESS, bar)
            self.entries.append(FileEntry(path=path, row=row))
        if skipped:
            self.statusBar().showMessage(f"Skipped {skipped} unsupported file(s).", 5000)
        self._update_buttons()

    def clear(self) -> None:
        if self._jobs:
            return
        self.entries.clear()
        self.table.setRowCount(0)
        self._update_buttons()

    def _browse_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUTS))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choose files", "", f"Supported files ({patterns});;All files (*)"
        )
        self.add_files([Path(f) for f in files])

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save converted files to")
        if folder:
            self.output_dir = Path(folder)
            self.output_button.setText(self.output_dir.name or str(self.output_dir))
            self.output_button.setToolTip(str(self.output_dir))
        else:
            self.output_dir = None
            self.output_button.setText("Same folder as original")
            self.output_button.setToolTip("")

    # ---- conversion ------------------------------------------------------

    def convert_all(self) -> None:
        output_format = self.format_combo.currentData()
        queued = 0
        for entry in self.entries:
            if entry.status in ("Queued", "Converting…", "Done"):  # only retry Ready/Failed/unsupported
                continue
            converter = self.registry.find(entry.path, output_format)
            if converter is None:
                self._set_status(entry, "Not supported yet")
                self.table.item(entry.row, COL_STATUS).setToolTip(
                    f"Converting {entry.path.suffix} files to {output_format.label} is coming in a later version."
                )
                continue
            destination = output_path_for(entry.path, output_format, self.output_dir)
            job = ConversionJob(entry.row, converter, entry.path, destination)
            job.signals.progress.connect(self._on_progress)
            job.signals.finished.connect(self._on_finished)
            job.signals.failed.connect(self._on_failed)
            self._jobs[entry.row] = job
            self._set_status(entry, "Queued")
            self._bar(entry).setValue(0)
            self.pool.start(job)
            queued += 1
        if queued:
            self.statusBar().showMessage(f"Converting {queued} file(s)…")
        self._update_buttons()

    def _on_progress(self, row: int, fraction: float) -> None:
        entry = self.entries[row]
        if entry.status != "Converting…":
            self._set_status(entry, "Converting…")
        self._bar(entry).setValue(int(fraction * 100))

    def _on_finished(self, row: int, output: str) -> None:
        entry = self.entries[row]
        entry.output = Path(output)
        self._bar(entry).setValue(100)
        self._set_status(entry, "Done")
        self.table.item(row, COL_STATUS).setToolTip(output)
        self._job_ended(row)

    def _on_failed(self, row: int, message: str) -> None:
        entry = self.entries[row]
        self._bar(entry).setValue(0)
        self._set_status(entry, "Failed")
        self.table.item(row, COL_STATUS).setToolTip(message)
        self._job_ended(row)

    def _job_ended(self, row: int) -> None:
        self._jobs.pop(row, None)
        if not self._jobs:
            done = sum(e.status == "Done" for e in self.entries)
            failed = sum(e.status == "Failed" for e in self.entries)
            msg = f"Finished: {done} converted"
            if failed:
                msg += f", {failed} failed (click a file to see why)"
            self.statusBar().showMessage(msg)
        self._update_buttons()

    def _open_result(self, row: int, _column: int) -> None:
        entry = self.entries[row]
        if entry.output and entry.output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(entry.output)))

    def _show_row_details(self, row: int, *_args) -> None:
        if 0 <= row < len(self.entries):
            detail = self.table.item(row, COL_STATUS).toolTip()
            if detail:
                self.statusBar().showMessage(detail)

    # ---- helpers ---------------------------------------------------------

    def _bar(self, entry: FileEntry) -> QProgressBar:
        return self.table.cellWidget(entry.row, COL_PROGRESS)

    def _set_status(self, entry: FileEntry, status: str) -> None:
        entry.status = status
        self.table.item(entry.row, COL_STATUS).setText(status)

    def _update_buttons(self) -> None:
        busy = bool(self._jobs)
        has_files = bool(self.entries)
        self.convert_button.setEnabled(has_files and not busy)
        self.clear_button.setEnabled(has_files and not busy)
        self.format_combo.setEnabled(not busy)
        self.output_button.setEnabled(not busy)
