"""Actions, converters and the registry.

An *action* is what the user picks in the window: "Word (.docx)", "Merge PDFs",
"Rotate pages" and so on. Each action can have options (shown as a small form)
and is carried out by one or more converters, one per kind of input file. The
UI asks the registry which converter handles a file for the chosen action, so
new tools are added by declaring an action and registering a converter, with
no UI changes.
"""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ProgressCallback = Callable[[float], None]
Options = dict[str, Any]

# Option kinds understood by the options form in the window.
CHOICE, TEXT, PASSWORD, PAGES, BOOL, NUMBER = "choice", "text", "password", "pages", "bool", "number"


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    kind: str = TEXT
    default: Any = None
    choices: tuple[tuple[str, Any], ...] = ()  # (label, value) pairs for CHOICE
    required: bool = False
    placeholder: str = ""
    minimum: int = 0
    maximum: int = 9999


@dataclass(frozen=True)
class Action:
    """Something the user can do to their files.

    extension: the output file's extension, or "" when the action writes a folder of files.
    suffix: added to the output name, e.g. "report (rotated).pdf".
    combine: True when all files go into one output (merge). A string names a BOOL
        option that switches combining on or off.
    """

    key: str
    label: str
    extension: str
    group: str = "Convert"
    description: str = ""
    suffix: str = ""
    options: tuple[Option, ...] = field(default=())
    combine: bool | str = False

    def is_combined(self, options: Options | None = None) -> bool:
        if isinstance(self.combine, str):
            return bool((options or {}).get(self.combine))
        return self.combine

    def default_options(self) -> Options:
        return {o.key: o.default for o in self.options}


# Kept for readability where an action is plainly a file format.
OutputFormat = Action

WORD = Action("docx", "Word (.docx)", ".docx", description="Converts each PDF into an editable Word document.")
EXCEL = Action("xlsx", "Excel (.xlsx)", ".xlsx", description="Puts the tables of each PDF into an Excel workbook.")

IMAGE_INPUTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp", ".heic", ".heif"}
SUPPORTED_INPUTS = {".pdf"} | IMAGE_INPUTS


class ConversionError(Exception):
    """Raised when a file cannot be converted. The message is shown to the user."""


class Converter(ABC):
    """Carries out one action for one kind of input.

    Single-file actions implement convert(); combining actions implement combine().
    Either may return a short note (for example "2.1 MB to 0.8 MB") shown next to the result.
    """

    input_extensions: frozenset[str] = frozenset()
    output_format: Action

    @property
    def action(self) -> Action:
        return self.output_format

    def convert(
        self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None
    ) -> str | None:
        raise NotImplementedError

    def combine(
        self, sources: list[Path], destination: Path, progress: ProgressCallback, options: Options | None = None
    ) -> str | None:
        raise NotImplementedError


class ConverterRegistry:
    def __init__(self) -> None:
        self._converters: list[Converter] = []

    def register(self, converter: Converter) -> None:
        self._converters.append(converter)

    def find(self, source: Path, action: Action) -> Converter | None:
        ext = source.suffix.lower()
        for converter in self._converters:
            if ext in converter.input_extensions and converter.output_format == action:
                return converter
        return None

    def extensions_for(self, action: Action) -> set[str]:
        return {ext for c in self._converters if c.output_format == action for ext in c.input_extensions}

    def actions(self) -> list[Action]:
        """Every registered action, in registration order, without duplicates."""
        seen: list[Action] = []
        for converter in self._converters:
            if converter.output_format not in seen:
                seen.append(converter.output_format)
        return seen


def output_path_for(source: Path, action: Action, output_dir: Path | None = None) -> Path:
    """Pick a destination next to the source (or in output_dir) without overwriting anything.

    Actions that write several files get a new folder instead of a file.
    """
    folder = output_dir or source.parent
    stem = f"{source.stem}{action.suffix}"
    candidate = folder / f"{stem}{action.extension}"
    n = 1
    while candidate.exists():
        candidate = folder / f"{stem} ({n}){action.extension}"
        n += 1
    return candidate


def file_size_note(before: int, after: int) -> str:
    def fmt(size: int) -> str:
        for unit in ("bytes", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.0f} {unit}" if unit == "bytes" else f"{size:.1f} {unit}"
            size /= 1024
        return ""

    if after < before:
        return f"{fmt(before)} to {fmt(after)} ({100 * (before - after) / before:.0f}% smaller)"
    return f"{fmt(before)} to {fmt(after)}"
