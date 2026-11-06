# File Converter

An offline desktop app for Windows, macOS and Linux that converts PDFs and images into Word and Excel files. Nothing is uploaded anywhere: every conversion runs on your own computer.

![Main window](docs/main-window.png)

## Status

| Conversion | Status |
| --- | --- |
| PDF → Word (.docx) | ✅ Text PDFs (layout, images and tables kept) |
| PDF → Excel (.xlsx) | ✅ Text PDFs (each page with tables becomes a sheet; numbers stay numbers) |
| Image / scanned PDF → Word or Excel (OCR) | Planned (step 3) |
| Installers for Windows, macOS, Linux | ✅ Built automatically, see below |

Scanned PDFs, password-protected PDFs and PDFs without tables (for Excel) are rejected with a clear message. Click a failed file to see why.

## Install

Download the latest installer from the [Releases page](https://github.com/SpOok548/file-converter/releases/latest):

- **Windows:** `FileConverter-Setup-<version>.exe`. Run it and follow the steps. Windows may show "Windows protected your PC" because the installer isn't code-signed yet; click **More info → Run anyway**.
- **macOS (Apple Silicon):** `FileConverter-<version>-macOS.dmg`. Open it and drag File Converter into Applications. The first time, right-click the app and choose **Open**, because it isn't notarized by Apple yet.
- **Linux:** `FileConverter-<version>-x86_64.AppImage`. Make it executable (`chmod +x`) and double-click it.

## Make a new release

1. Bump `__version__` in `src/file_converter/__init__.py` and `version` in `pyproject.toml`.
2. Tag and push: `git tag v0.2.0 && git push origin v0.2.0`.
3. GitHub Actions builds all three installers, tests that each one converts a PDF, and publishes them as a release.

To build installers without releasing, open **Actions → Build installers → Run workflow**.

## Command line

```bash
file-converter --convert report.pdf --to xlsx --output report.xlsx
```

## Run from source

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m file_converter
```

## Run the tests

```bash
pytest
```

## How it's organised

- `src/file_converter/ui/main_window.py`: the window (drag and drop, file list, format picker, Convert button).
- `src/file_converter/worker.py`: runs each conversion in the background so the window never freezes.
- `src/file_converter/converters/`: one class per conversion. To add a conversion, subclass `Converter`, set `input_extensions` and `output_format`, implement `convert()`, and register it in `default_registry()`.

## Licensing note

PDF to Word uses [pdf2docx](https://github.com/ArtifexSoftware/pdf2docx), which depends on PyMuPDF. PyMuPDF is licensed under the GNU AGPL 3.0 (or a paid Artifex commercial licence), so a published build of this app must either be released under the AGPL with its source available, or use a commercial PyMuPDF licence.
