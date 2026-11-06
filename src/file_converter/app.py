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
from file_converter.converters import OUTPUT_FORMATS, ConversionError, default_registry, output_path_for


def convert_cli(source: Path, format_key: str, output: Path | None) -> int:
    fmt = next(f for f in OUTPUT_FORMATS if f.key == format_key)
    converter = default_registry().find(source, fmt)
    if converter is None:
        print(f"Converting {source.suffix} files to {fmt.label} isn't supported yet.", file=sys.stderr)
        return 2
    destination = output or output_path_for(source, fmt)
    try:
        converter.convert(source, destination, lambda _fraction: None)
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
    parser.add_argument("--to", choices=[f.key for f in OUTPUT_FORMATS], default="docx")
    parser.add_argument("--output", type=Path)
    args, qt_args = parser.parse_known_args(argv[1:])
    if args.convert:
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
