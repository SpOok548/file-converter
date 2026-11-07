"""Main window: add files, pick a tool, set its options, start, see results."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from file_converter.converters import SUPPORTED_INPUTS, Action, ConverterRegistry, Options, output_path_for
from file_converter.converters.base import BOOL, CHOICE, NUMBER, PASSWORD, Option
from file_converter.worker import ConversionJob

COL_FILE, COL_STATUS, COL_PROGRESS = range(3)
BUSY = ("Queued", "Converting…")


@dataclass
class FileEntry:
    path: Path
    status: str = "Ready"
    output: Path | None = None
    detail: str = ""
    progress: int = 0
    note: str = ""


class DropArea(QFrame):
    def __init__(self, on_files, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_files = on_files
        self.setAcceptDrops(True)
        self.setObjectName("dropArea")
        self.setMinimumHeight(96)
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
        hint = QLabel("PDF, PNG, JPG, HEIC, BMP, TIFF, WEBP")
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
        self._jobs: dict[int, tuple[ConversionJob, list[FileEntry]]] = {}
        self._next_job = 0
        self._option_widgets: dict[str, QWidget] = {}
        self._saved_options: dict[str, Options] = {}
        self._action: Action | None = None

        self.setWindowTitle("File Converter")
        self.resize(820, 640)

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
        self.table.itemSelectionChanged.connect(self._update_buttons)
        root.addWidget(self.table, 1)

        file_row = QHBoxLayout()
        self.add_button = QPushButton("Add files…")
        self.add_button.clicked.connect(self._browse_files)
        self.up_button = QPushButton("Move up")
        self.up_button.clicked.connect(lambda: self.move_selected(-1))
        self.down_button = QPushButton("Move down")
        self.down_button.clicked.connect(lambda: self.move_selected(1))
        self.remove_button = QPushButton("Remove")
        self.remove_button.clicked.connect(self.remove_selected)
        self.clear_button = QPushButton("Clear list")
        self.clear_button.clicked.connect(self.clear)
        for button in (self.add_button, self.up_button, self.down_button, self.remove_button, self.clear_button):
            file_row.addWidget(button)
        file_row.addStretch()
        root.addLayout(file_row)

        action_row = QHBoxLayout()
        action_row.addWidget(QLabel("Tool:"))
        self.action_combo = QComboBox()
        self.action_combo.setMinimumWidth(240)
        self._fill_action_combo()
        action_row.addWidget(self.action_combo)
        action_row.addSpacing(16)
        action_row.addWidget(QLabel("Save to:"))
        self.output_button = QPushButton("Same folder as original")
        self.output_button.clicked.connect(self._choose_output_dir)
        action_row.addWidget(self.output_button)
        action_row.addStretch()
        self.convert_button = QPushButton("Start")
        self.convert_button.setDefault(True)
        self.convert_button.clicked.connect(self.convert_all)
        action_row.addWidget(self.convert_button)
        root.addLayout(action_row)

        self.description = QLabel()
        self.description.setWordWrap(True)
        root.addWidget(self.description)

        self.options_box = QGroupBox("Options")
        self.options_form = QFormLayout(self.options_box)
        root.addWidget(self.options_box)

        self.setCentralWidget(central)
        self.action_combo.currentIndexChanged.connect(self._action_changed)
        self._action_changed()
        self.statusBar().showMessage("Add files to get started. Double-click a finished file to open it.")
        self._update_buttons()

    # ---- tools and options ----------------------------------------------

    def _fill_action_combo(self) -> None:
        model = self.action_combo.model()
        group = None
        for action in self.registry.actions():
            if action.group != group:
                group = action.group
                if self.action_combo.count():
                    self.action_combo.insertSeparator(self.action_combo.count())
                self.action_combo.addItem(group.upper())
                header = model.item(self.action_combo.count() - 1)
                header.setEnabled(False)
                font = header.font()
                font.setBold(True)
                header.setFont(font)
            self.action_combo.addItem(f"   {action.label}", action)
        for index in range(self.action_combo.count()):
            if self.action_combo.itemData(index) is not None:
                self.action_combo.setCurrentIndex(index)
                break

    @property
    def format_combo(self) -> QComboBox:  # older name, kept for tests and scripts
        return self.action_combo

    def current_action(self) -> Action | None:
        return self.action_combo.currentData()

    def select_action(self, action: Action) -> None:
        self.action_combo.setCurrentIndex(self.action_combo.findData(action))

    def _action_changed(self, *_args) -> None:
        if self._action is not None:
            self._saved_options[self._action.key] = self.option_values()
        action = self.current_action()
        self._action = action
        while self.options_form.rowCount():
            self.options_form.removeRow(0)
        self._option_widgets.clear()
        if action is None:
            return
        self.description.setText(action.description)
        saved = self._saved_options.get(action.key, {})
        for option in action.options:
            widget = self._make_option_widget(option, saved.get(option.key, option.default))
            self._option_widgets[option.key] = widget
            if option.kind == BOOL:
                self.options_form.addRow("", widget)
            else:
                self.options_form.addRow(f"{option.label}:", widget)
        self.options_box.setVisible(bool(action.options))
        self._reset_finished()

    def _make_option_widget(self, option: Option, value) -> QWidget:
        if option.kind == CHOICE:
            widget = QComboBox()
            for label, choice in option.choices:
                widget.addItem(label, choice)
            index = next((i for i, (_, c) in enumerate(option.choices) if c == value), 0)
            widget.setCurrentIndex(index)
            widget.currentIndexChanged.connect(self._reset_finished)
        elif option.kind == BOOL:
            widget = QCheckBox(option.label)
            widget.setChecked(bool(value))
            widget.toggled.connect(self._reset_finished)
        elif option.kind == NUMBER:
            widget = QSpinBox()
            widget.setRange(option.minimum, option.maximum)
            widget.setValue(int(value if value is not None else option.minimum))
            widget.valueChanged.connect(self._reset_finished)
        else:
            widget = QLineEdit()
            widget.setText("" if value is None else str(value))
            widget.setPlaceholderText(option.placeholder)
            if option.kind == PASSWORD:
                widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.textEdited.connect(self._reset_finished)
        return widget

    def option_values(self) -> Options:
        values: Options = {}
        for key, widget in self._option_widgets.items():
            if isinstance(widget, QComboBox):
                values[key] = widget.currentData()
            elif isinstance(widget, QCheckBox):
                values[key] = widget.isChecked()
            elif isinstance(widget, QSpinBox):
                values[key] = widget.value()
            elif isinstance(widget, QLineEdit):
                values[key] = widget.text()
        return values

    def set_option(self, key: str, value) -> None:
        widget = self._option_widgets[key]
        if isinstance(widget, QComboBox):
            widget.setCurrentIndex(widget.findData(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        else:
            widget.setText(str(value))

    def _reset_finished(self, *_args) -> None:
        """A different tool or setting means finished files can be processed again."""
        for row, entry in enumerate(self.entries):
            if entry.status not in BUSY and entry.status != "Ready":
                entry.status, entry.detail, entry.note, entry.progress = "Ready", "", "", 0
                self._render_row(row)

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
            self.entries.append(FileEntry(path=path))
            row = self.table.rowCount()
            self.table.insertRow(row)
            self._render_row(row)
        if skipped:
            self.statusBar().showMessage(f"Skipped {skipped} unsupported file(s).", 5000)
        self._update_buttons()

    def clear(self) -> None:
        if self._jobs:
            return
        self.entries.clear()
        self.table.setRowCount(0)
        self._update_buttons()

    def _selected_rows(self) -> list[int]:
        return sorted({index.row() for index in self.table.selectionModel().selectedRows()})

    def move_selected(self, step: int) -> None:
        rows = self._selected_rows()
        if self._jobs or not rows:
            return
        if (step < 0 and rows[0] == 0) or (step > 0 and rows[-1] == len(self.entries) - 1):
            return
        for row in rows if step < 0 else reversed(rows):
            self.entries[row], self.entries[row + step] = self.entries[row + step], self.entries[row]
        for row in range(len(self.entries)):
            self._render_row(row)
        self.table.clearSelection()
        mode = self.table.selectionMode()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for row in rows:
            self.table.selectRow(row + step)
        self.table.setSelectionMode(mode)

    def remove_selected(self) -> None:
        if self._jobs:
            return
        for row in reversed(self._selected_rows()):
            del self.entries[row]
            self.table.removeRow(row)
        self._update_buttons()

    def _render_row(self, row: int) -> None:
        entry = self.entries[row]
        item = QTableWidgetItem(entry.path.name)
        item.setToolTip(str(entry.path))
        self.table.setItem(row, COL_FILE, item)
        status = f"{entry.status}: {entry.note}" if entry.note else entry.status
        status_item = QTableWidgetItem(status)
        status_item.setToolTip(entry.detail)
        self.table.setItem(row, COL_STATUS, status_item)
        bar = self.table.cellWidget(row, COL_PROGRESS)
        if bar is None:
            bar = QProgressBar()
            bar.setRange(0, 100)
            self.table.setCellWidget(row, COL_PROGRESS, bar)
        bar.setValue(entry.progress)

    def _browse_files(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUTS))
        files, _ = QFileDialog.getOpenFileNames(
            self, "Choose files", "", f"Supported files ({patterns});;All files (*)"
        )
        self.add_files([Path(f) for f in files])

    def _choose_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Save results to")
        if folder:
            self.output_dir = Path(folder)
            self.output_button.setText(self.output_dir.name or str(self.output_dir))
            self.output_button.setToolTip(str(self.output_dir))
        else:
            self.output_dir = None
            self.output_button.setText("Same folder as original")
            self.output_button.setToolTip("")

    # ---- running ---------------------------------------------------------

    def convert_all(self) -> None:
        action = self.current_action()
        if action is None:
            return
        options = self.option_values()
        for option in action.options:
            if option.required and not str(options.get(option.key) or "").strip():
                self.statusBar().showMessage(f"Fill in \"{option.label}\" first.", 6000)
                self._option_widgets[option.key].setFocus()
                return

        ready = []
        for entry in self.entries:
            if entry.status in BUSY or entry.status == "Done":
                continue
            converter = self.registry.find(entry.path, action)
            if converter is None:
                self._mark_unsupported(entry, action)
            else:
                ready.append((entry, converter))

        if action.is_combined(options):
            if ready:
                converter = ready[0][1]
                group = [entry for entry, c in ready if c is converter]
                for entry, c in ready:
                    if c is not converter:
                        self._mark_unsupported(entry, action)
                destination = output_path_for(group[0].path, action, self.output_dir)
                self._start_job(converter, group, destination, options)
            queued = len(ready)
        else:
            for entry, converter in ready:
                destination = output_path_for(entry.path, action, self.output_dir)
                self._start_job(converter, [entry], destination, options)
            queued = len(ready)
        if queued:
            self.statusBar().showMessage(f"Working on {queued} file(s)…")
        self._update_buttons()

    def _mark_unsupported(self, entry: FileEntry, action: Action) -> None:
        accepted = ", ".join(sorted(e.lstrip(".").upper() for e in self.registry.extensions_for(action)))
        if action.group == "Convert" and entry.path.suffix.lower() != ".pdf":
            entry.status = "Not supported yet"
            entry.detail = f"Converting {entry.path.suffix} files to {action.label} is coming in a later version."
        else:
            entry.status = "Skipped"
            entry.detail = f"\"{action.label}\" works on {accepted} files."
        entry.note = ""
        self._render_row(self._row_of(entry))

    def _start_job(self, converter, group: list[FileEntry], destination: Path, options: Options) -> None:
        job_id = self._next_job
        self._next_job += 1
        job = ConversionJob(job_id, converter, [e.path for e in group], destination, options)
        job.signals.progress.connect(self._on_progress)
        job.signals.finished.connect(self._on_finished)
        job.signals.failed.connect(self._on_failed)
        self._jobs[job_id] = (job, group)
        for entry in group:
            entry.status, entry.detail, entry.note, entry.progress, entry.output = "Queued", "", "", 0, None
            self._render_row(self._row_of(entry))
        self.pool.start(job)

    def _job_entries(self, job_id: int) -> list[FileEntry]:
        return self._jobs[job_id][1] if job_id in self._jobs else []

    def _on_progress(self, job_id: int, fraction: float) -> None:
        for entry in self._job_entries(job_id):
            entry.status = "Converting…"
            entry.progress = int(fraction * 100)
            self._render_row(self._row_of(entry))

    def _on_finished(self, job_id: int, output: str, note: str) -> None:
        for entry in self._job_entries(job_id):
            entry.status, entry.output, entry.progress, entry.note = "Done", Path(output), 100, note
            entry.detail = f"{output}\n{note}" if note else output
            self._render_row(self._row_of(entry))
        self._job_ended(job_id)

    def _on_failed(self, job_id: int, message: str) -> None:
        for entry in self._job_entries(job_id):
            entry.status, entry.progress, entry.detail, entry.note = "Failed", 0, message, ""
            self._render_row(self._row_of(entry))
        self._job_ended(job_id)

    def _job_ended(self, job_id: int) -> None:
        self._jobs.pop(job_id, None)
        if not self._jobs:
            done = sum(e.status == "Done" for e in self.entries)
            failed = sum(e.status == "Failed" for e in self.entries)
            msg = f"Finished: {done} done"
            if failed:
                msg += f", {failed} failed (click a file to see why)"
            self.statusBar().showMessage(msg)
        self._update_buttons()

    def _open_result(self, row: int, _column: int) -> None:
        entry = self.entries[row]
        if entry.output and entry.output.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(entry.output)))

    def _show_row_details(self, row: int, *_args) -> None:
        if 0 <= row < len(self.entries) and self.entries[row].detail:
            self.statusBar().showMessage(self.entries[row].detail.replace("\n", "  ·  "))

    # ---- helpers ---------------------------------------------------------

    def _row_of(self, entry: FileEntry) -> int:
        return next(row for row, e in enumerate(self.entries) if e is entry)

    def _update_buttons(self) -> None:
        busy = bool(self._jobs)
        has_files = bool(self.entries)
        selected = bool(self.table.selectionModel().selectedRows()) if self.table.selectionModel() else False
        self.convert_button.setEnabled(has_files and not busy)
        self.clear_button.setEnabled(has_files and not busy)
        for button in (self.up_button, self.down_button, self.remove_button):
            button.setEnabled(selected and not busy)
        self.action_combo.setEnabled(not busy)
        self.options_box.setEnabled(not busy)
        self.output_button.setEnabled(not busy)
