"""Runs conversions off the UI thread so the window stays responsive."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from file_converter.converters import ConversionError, Converter


class JobSignals(QObject):
    progress = Signal(int, float)  # job id, 0.0..1.0
    finished = Signal(int, str)  # job id, output path
    failed = Signal(int, str)  # job id, message


class ConversionJob(QRunnable):
    def __init__(self, job_id: int, converter: Converter, source: Path, destination: Path) -> None:
        super().__init__()
        self.job_id = job_id
        self.converter = converter
        self.source = source
        self.destination = destination
        self.signals = JobSignals()

    def run(self) -> None:
        try:
            self.converter.convert(
                self.source,
                self.destination,
                lambda fraction: self.signals.progress.emit(self.job_id, max(0.0, min(1.0, fraction))),
            )
        except ConversionError as exc:
            self._cleanup()
            self.signals.failed.emit(self.job_id, str(exc))
        except Exception as exc:  # noqa: BLE001 - any crash must surface in the UI, not kill the app
            self._cleanup()
            self.signals.failed.emit(self.job_id, f"Unexpected error: {exc}")
        else:
            self.signals.finished.emit(self.job_id, str(self.destination))

    def _cleanup(self) -> None:
        try:
            self.destination.unlink(missing_ok=True)
        except OSError:
            pass
