"""Converter interface and registry.

Each converter turns one kind of input file into one output format. The UI
asks the registry which converter handles a given file and target format, so
new conversions are added by registering a converter, with no UI changes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

ProgressCallback = Callable[[float], None]


@dataclass(frozen=True)
class OutputFormat:
    key: str
    label: str
    extension: str


WORD = OutputFormat("docx", "Word (.docx)", ".docx")
EXCEL = OutputFormat("xlsx", "Excel (.xlsx)", ".xlsx")
OUTPUT_FORMATS = (WORD, EXCEL)

SUPPORTED_INPUTS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


class ConversionError(Exception):
    """Raised when a file cannot be converted. The message is shown to the user."""


class Converter(ABC):
    input_extensions: frozenset[str] = frozenset()
    output_format: OutputFormat

    @abstractmethod
    def convert(self, source: Path, destination: Path, progress: ProgressCallback) -> None:
        """Convert source to destination, reporting progress from 0.0 to 1.0."""


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: list[Converter] = []

    def register(self, converter: Converter) -> None:
        self._converters.append(converter)

    def find(self, source: Path, output_format: OutputFormat) -> Converter | None:
        ext = source.suffix.lower()
        for converter in self._converters:
            if ext in converter.input_extensions and converter.output_format == output_format:
                return converter
        return None


def output_path_for(source: Path, output_format: OutputFormat, output_dir: Path | None = None) -> Path:
    """Pick a destination next to the source (or in output_dir) without overwriting anything."""
    folder = output_dir or source.parent
    candidate = folder / f"{source.stem}{output_format.extension}"
    n = 1
    while candidate.exists():
        candidate = folder / f"{source.stem} ({n}){output_format.extension}"
        n += 1
    return candidate
