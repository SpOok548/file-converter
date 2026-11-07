"""PDF to Word, keeping layout, fonts, images and tables as closely as pdf2docx can."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from file_converter.converters.base import WORD, ConversionError, Converter, ProgressCallback
from file_converter.converters.pdf_common import SCANNED_MESSAGE, inspect_pdf

_PAGE_LOG = re.compile(r"\((\d+)/(\d+)\)")


class _ProgressFromLog(logging.Handler):
    """pdf2docx reports per-page progress only through log lines like "(3/10) Page 3"."""

    def __init__(self, progress: ProgressCallback) -> None:
        super().__init__(logging.INFO)
        self.progress = progress
        self.phase = 0  # 0 = parsing (0-80%), 1 = writing (80-100%)

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if "Creating pages" in msg:
            self.phase = 1
        match = _PAGE_LOG.search(msg)
        if match:
            done, total = int(match.group(1)), int(match.group(2))
            fraction = done / max(total, 1)
            self.progress(0.8 * fraction if self.phase == 0 else 0.8 + 0.2 * fraction)


class PdfToWord(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = WORD

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options=None) -> None:
        info = inspect_pdf(source)
        if not info.has_text:
            raise ConversionError(SCANNED_MESSAGE)

        from pdf2docx import Converter as Pdf2Docx

        logger = logging.getLogger()
        handler = _ProgressFromLog(progress)
        previous_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(min(previous_level or logging.WARNING, logging.INFO))
        progress(0.02)
        try:
            pdf = Pdf2Docx(str(source))
            try:
                pdf.convert(str(destination))
            finally:
                pdf.close()
        except ConversionError:
            raise
        except Exception as exc:  # noqa: BLE001 - surface any library failure as a readable message
            raise ConversionError(f"Couldn't convert this PDF to Word: {exc}") from exc
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
        progress(1.0)
