# PyInstaller build recipe. Run from the repo root:  pyinstaller packaging/file_converter.spec
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT / "src"))
from file_converter import __version__  # noqa: E402

ICON = str(ROOT / "packaging" / "icon.png")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=collect_data_files("file_converter") + collect_data_files("pdf2docx"),
    hiddenimports=collect_submodules("pdf2docx") + collect_submodules("file_converter.converters"),
    excludes=[
        "tkinter", "matplotlib", "IPython", "pytest",
        # Qt modules this app never uses; leaving them out shrinks the download.
        "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtQuickWidgets",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtMultimedia",
        "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ],
)
# Qt plugins drag in Quick/QML/PDF/virtual-keyboard libraries the app never loads.
_UNUSED = ("qt6quick", "qt6qml", "qt6pdf", "virtualkeyboard", "qtquick", "qtqml", "qtpdf", "qpdf.", "libqpdf")
a.binaries = [b for b in a.binaries if not any(u in b[0].lower().replace("\\", "/") for u in _UNUSED)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="File Converter",
    console=False,
    icon=ICON,
)
coll = COLLECT(exe, a.binaries, a.datas, name="File Converter")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="File Converter.app",
        icon=ICON,
        bundle_identifier="io.github.spook548.fileconverter",
        version=__version__,
        info_plist={"NSHighResolutionCapable": True, "LSMinimumSystemVersion": "11.0"},
    )
