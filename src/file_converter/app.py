"""Application entry point.

Running with no arguments opens the window. A small command-line mode is also
available, which the installer builds use as a smoke test:

    "File Converter" --convert report.pdf --to xlsx [--output out.xlsx]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from file_converter import __version__
from file_converter.converters import ConversionError, default_registry, output_path_for


def convert_cli(source: Path, action_key: str, output: Path | None) -> int:
    registry = default_registry()
    action = next(a for a in registry.actions() if a.key == action_key)
    converter = registry.find(source, action)
    if converter is None:
        print(f"{action.label} doesn't work on {source.suffix} files.", file=sys.stderr)
        return 2
    destination = output or output_path_for(source, action)
    try:
        if action.is_combined(action.default_options()):
            converter.combine([source], destination, lambda _fraction: None, action.default_options())
        else:
            converter.convert(source, destination, lambda _fraction: None, action.default_options())
    except ConversionError as exc:
        print(f"Failed: {exc}", file=sys.stderr)
        return 1
    print(destination)
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    parser = argparse.ArgumentParser(prog="file-converter", add_help=True)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--convert", type=Path, metavar="FILE", help="convert FILE without opening the window")
    parser.add_argument("--to", metavar="TOOL", default="docx", help="tool to run, e.g. docx, xlsx, compress")
    parser.add_argument("--output", type=Path)
    args, qt_args = parser.parse_known_args(argv[1:])
    if args.convert:
        keys = [a.key for a in default_registry().actions()]
        if args.to not in keys:
            parser.error(f"--to must be one of: {', '.join(keys)}")
        return convert_cli(args.convert, args.to, args.output)

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from file_converter.ui.main_window import MainWindow

    app = QApplication([argv[0], *qt_args])
    app.setApplicationName("File Converter")
    app.setApplicationVersion(__version__)
    icon = Path(__file__).parent / "resources" / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))
    window = MainWindow(default_registry())
    window.show()
    return app.exec()
