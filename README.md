# File Converter

An offline desktop app for Windows, macOS and Linux that converts PDFs and images into Word and Excel files. Nothing is uploaded anywhere: every conversion runs on your own computer.

![Main window](docs/main-window.png)

## Status

| Conversion | Status |
| --- | --- |
| PDF → Word (.docx) | Planned (step 2) |
| PDF → Excel (.xlsx) | Planned (step 2) |
| Image / scanned PDF → Word or Excel (OCR) | Planned (step 3) |
| Installers for Windows, macOS, Linux | Planned (step 4) |

The app window, file list, progress tracking and converter framework are in place.

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
