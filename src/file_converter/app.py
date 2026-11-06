"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from file_converter import __version__
from file_converter.converters import default_registry
from file_converter.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("File Converter")
    app.setApplicationVersion(__version__)
    window = MainWindow(default_registry())
    window.show()
    return app.exec()
