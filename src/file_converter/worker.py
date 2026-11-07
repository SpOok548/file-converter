"""Runs conversions off the UI thread so the window stays responsive."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRunnable, Signal

from file_converter.converters import ConversionError, Converter, Options

ProgressFn = Callable[[float], None]


class JobSignals(QObject):
    progress = Signal(int, float)  # job id, 0.0..1.0
    finished = Signal(int, str, str)  # job id, output path, note ("" when none)
    failed = Signal(int, str)  # job id, message


class ConversionJob(QRunnable):
    """One unit of work: one file, or several files that combine into one output (merge)."""

    def __init__(
        self,
        job_id: int,
        converter: Converter,
        sources: Path | list[Path],
        destination: Path,
        options: Options | None = None,
    ) -> None:
        super().__init__()
        self.job_id = job_id
        self.converter = converter
        self.sources = [sources] if isinstance(sources, Path) else list(sources)
        self.destination = destination
        self.options = dict(options or {})
        self.signals = JobSignals()

    @property
    def source(self) -> Path:
        return self.sources[0]

    def run(self) -> None:
        report: ProgressFn = lambda fraction: self.signals.progress.emit(  # noqa: E731
            self.job_id, max(0.0, min(1.0, fraction))
        )
        try:
            if self.converter.action.is_combined(self.options):
                note = self.converter.combine(self.sources, self.destination, report, self.options)
            else:
                note = self.converter.convert(self.source, self.destination, report, self.options)
        except ConversionError as exc:
            self._cleanup()
            self.signals.failed.emit(self.job_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - any crash must surface in the UI, not kill the app
            self._cleanup()
            self.signals.failed.emit(self.job_id, f"Unexpected error: {exc}")
        else:
            self.signals.finished.emit(self.job_id, str(self.destination), note or "")

    def _cleanup(self) -> None:
        # The destination was picked so that it didn't exist before, so anything there is ours.
        try:
            if self.destination.is_dir():
                shutil.rmtree(self.destination, ignore_errors=True)
            else:
                self.destination.unlink(missing_ok=True)
        except OSError:
            pass
