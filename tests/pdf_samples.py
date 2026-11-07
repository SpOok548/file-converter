"""Builds small PDFs for tests with PyMuPDF, so no binary fixtures live in the repo."""

from pathlib import Path

import pymupdf

INVOICE_ROWS = [
    ["Item", "Qty", "Price"],
    ["Paper", "2", "4.50"],
    ["Ink", "1", "1,250.00"],
    ["Stapler", "3", "(12.00)"],
]


def ruled_table_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 60), "Invoice 0042", fontsize=16)
    x0, y0, col_w, row_h = 72, 90, 120, 24
    for r, row in enumerate(INVOICE_ROWS):
        for c, text in enumerate(row):
            page.insert_text((x0 + c * col_w + 6, y0 + r * row_h + 16), text, fontsize=11)
    for r in range(len(INVOICE_ROWS) + 1):
        page.draw_line((x0, y0 + r * row_h), (x0 + 3 * col_w, y0 + r * row_h))
    for c in range(4):
        page.draw_line((x0 + c * col_w, y0), (x0 + c * col_w, y0 + len(INVOICE_ROWS) * row_h))
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Thank you for your business.", fontsize=12)
    doc.save(path)
    return path


def text_only_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Dear reader,", fontsize=12)
    page.insert_text((72, 96), "This letter has paragraphs but no tables.", fontsize=12)
    doc.save(path)
    return path


def scanned_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
    pix.clear_with(200)
    page.insert_image(pymupdf.Rect(72, 72, 300, 300), pixmap=pix)
    doc.save(path)
    return path


def password_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "secret")
    doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    return path


def numbered_pdf(path: Path, pages: int = 5) -> Path:
    """A PDF whose pages say "Page 1", "Page 2", ... so tests can tell them apart."""
    doc = pymupdf.open()
    for n in range(1, pages + 1):
        doc.new_page().insert_text((72, 72), f"Page {n}", fontsize=14)
    doc.save(path)
    return path


def page_texts(path: Path, password: str | None = None) -> list[str]:
    doc = pymupdf.open(path)
    if password:
        doc.authenticate(password)
    with doc:
        return [page.get_text().strip() for page in doc]


def photo_pdf(path: Path) -> Path:
    """One page holding a large, noisy photo-like image, so compression has something to do."""
    import random

    from PIL import Image

    rng = random.Random(1)
    image = Image.new("RGB", (1600, 1200))
    image.putdata([(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(1600 * 1200)])
    doc = pymupdf.open()
    page = doc.new_page()
    buffer = __import__("io").BytesIO()
    image.save(buffer, "PNG")
    page.insert_image(page.rect, stream=buffer.getvalue())
    doc.save(path)
    return path


def form_pdf(path: Path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    widget = pymupdf.Widget()
    widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    widget.field_name = "name"
    widget.field_value = "Ada"
    widget.rect = pymupdf.Rect(72, 72, 300, 100)
    page.add_widget(widget)
    page.add_text_annot((72, 200), "A sticky note")
    doc.save(path)
    return path
