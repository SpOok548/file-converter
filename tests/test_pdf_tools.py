"""The PDF toolkit: organize, optimize, edit, security and image tools."""

import pymupdf
import pytest
from PIL import Image
from pdf_samples import form_pdf, numbered_pdf, page_texts, password_pdf, photo_pdf, ruled_table_pdf

from file_converter.converters import ConversionError, default_registry
from file_converter.converters.images import ExtractImages, ImagesToPdf, PdfToJpg, PdfToPng
from file_converter.converters.pdf_common import page_groups, parse_pages
from file_converter.converters.pdf_edit import AddPageNumbers, AddWatermark, CompressPdf, FlattenPdf
from file_converter.converters.pdf_pages import ExtractPages, MergePdfs, RemovePages, RotatePages, SplitPdf
from file_converter.converters.pdf_security import ProtectPdf, UnlockPdf


def noop(_fraction):
    pass


# ---- page ranges ------------------------------------------------------------


def test_parse_pages():
    assert parse_pages("", 5) == [0, 1, 2, 3, 4]
    assert parse_pages("1-2, 4", 5) == [0, 1, 3]
    assert parse_pages("4-", 5) == [3, 4]
    assert parse_pages("3, 1-2, 2", 5) == [2, 0, 1]
    assert parse_pages("2-99", 3) == [1, 2]
    for bad in ("abc", "0", "3-1", "9"):
        with pytest.raises(ConversionError):
            parse_pages(bad, 5)


def test_page_groups():
    assert page_groups("", 3) == [[0], [1], [2]]
    assert page_groups("1-2, 3-", 5) == [[0, 1], [2, 3, 4]]


# ---- organize ---------------------------------------------------------------


def test_merge_keeps_list_order(tmp_path):
    a = numbered_pdf(tmp_path / "a.pdf", 2)
    b = ruled_table_pdf(tmp_path / "b.pdf")
    out = tmp_path / "merged.pdf"
    note = MergePdfs().combine([b, a], out, noop)
    texts = page_texts(out)
    assert len(texts) == 4
    assert texts[0].startswith("Invoice") and texts[2] == "Page 1"
    assert note == "2 files, 4 pages"


def test_merge_needs_two_files_and_no_passwords(tmp_path):
    a = numbered_pdf(tmp_path / "a.pdf", 1)
    with pytest.raises(ConversionError, match="at least two"):
        MergePdfs().combine([a], tmp_path / "m.pdf", noop)
    with pytest.raises(ConversionError, match="password"):
        MergePdfs().combine([a, password_pdf(tmp_path / "p.pdf")], tmp_path / "m.pdf", noop)


def test_split_every_page_and_ranges(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 4)
    out = tmp_path / "doc (split)"
    SplitPdf().convert(src, out, noop, {"ranges": ""})
    assert sorted(p.name for p in out.iterdir()) == [f"doc p{n}.pdf" for n in range(1, 5)]

    out2 = tmp_path / "ranges"
    SplitPdf().convert(src, out2, noop, {"ranges": "1-2, 3-"})
    assert sorted(p.name for p in out2.iterdir()) == ["doc p1-2.pdf", "doc p3-4.pdf"]
    assert page_texts(out2 / "doc p3-4.pdf") == ["Page 3", "Page 4"]


def test_extract_and_remove_pages(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 5)
    ExtractPages().convert(src, tmp_path / "x.pdf", noop, {"pages": "4, 1-2"})
    assert page_texts(tmp_path / "x.pdf") == ["Page 4", "Page 1", "Page 2"]
    RemovePages().convert(src, tmp_path / "r.pdf", noop, {"pages": "2-3"})
    assert page_texts(tmp_path / "r.pdf") == ["Page 1", "Page 4", "Page 5"]
    with pytest.raises(ConversionError, match="every page"):
        RemovePages().convert(src, tmp_path / "r2.pdf", noop, {"pages": "1-"})


def test_rotate_selected_pages(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 3)
    RotatePages().convert(src, tmp_path / "rot.pdf", noop, {"angle": 90, "pages": "2-"})
    RotatePages().convert(tmp_path / "rot.pdf", tmp_path / "rot2.pdf", noop, {"angle": 270, "pages": ""})
    with pymupdf.open(tmp_path / "rot2.pdf") as doc:
        assert [p.rotation for p in doc] == [270, 0, 0]


# ---- security ---------------------------------------------------------------


def test_protect_then_unlock(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 1)
    locked = tmp_path / "locked.pdf"
    ProtectPdf().convert(src, locked, noop, {"password": "s3cret"})
    with pymupdf.open(locked) as doc:
        assert doc.needs_pass
    with pytest.raises(ConversionError, match="password"):
        ProtectPdf().convert(locked, tmp_path / "again.pdf", noop, {"password": "x"})
    with pytest.raises(ConversionError, match="wrong"):
        UnlockPdf().convert(locked, tmp_path / "bad.pdf", noop, {"password": "nope"})
    UnlockPdf().convert(locked, tmp_path / "open.pdf", noop, {"password": "s3cret"})
    with pymupdf.open(tmp_path / "open.pdf") as doc:
        assert not doc.needs_pass and doc.metadata.get("encryption") is None
    assert page_texts(tmp_path / "open.pdf") == ["Page 1"]
    with pytest.raises(ConversionError, match="doesn't have a password"):
        UnlockPdf().convert(src, tmp_path / "plain.pdf", noop, {"password": "x"})


def test_unlock_permissions_only_pdf(tmp_path):
    src = tmp_path / "restricted.pdf"
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), "Hello")
    doc.save(src, encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="", permissions=0)
    with pytest.raises(ConversionError, match="wrong"):
        UnlockPdf().convert(src, tmp_path / "bad.pdf", noop, {"password": "nope"})
    UnlockPdf().convert(src, tmp_path / "ok.pdf", noop, {"password": "owner"})
    with pymupdf.open(tmp_path / "ok.pdf") as out:
        assert out.metadata.get("encryption") is None


# ---- optimize and edit ------------------------------------------------------


def test_compress_shrinks_big_images(tmp_path):
    src = photo_pdf(tmp_path / "photo.pdf")
    out = tmp_path / "small.pdf"
    note = CompressPdf().convert(src, out, noop, {"level": "strong"})
    assert out.stat().st_size < src.stat().st_size / 2
    assert "smaller" in note


def test_compress_reports_when_nothing_to_gain(tmp_path):
    src = tmp_path / "tiny.pdf"
    CompressPdf().convert(photo_pdf(tmp_path / "photo.pdf"), src, noop, {"level": "strong"})
    out = tmp_path / "again.pdf"
    with pytest.raises(ConversionError, match="already as small"):
        CompressPdf().convert(src, out, noop, {"level": "strong"})
    assert not out.exists()


def test_flatten_removes_fields_and_notes(tmp_path):
    src = form_pdf(tmp_path / "form.pdf")
    out = tmp_path / "flat.pdf"
    note = FlattenPdf().convert(src, out, noop)
    with pymupdf.open(out) as doc:
        assert not list(doc[0].widgets()) and not list(doc[0].annots())
        assert "Ada" in doc[0].get_text()
    assert note == "1 form field(s) and 1 comment(s) flattened"
    with pytest.raises(ConversionError, match="no form fields"):
        FlattenPdf().convert(numbered_pdf(tmp_path / "plain.pdf", 1), tmp_path / "x.pdf", noop)


def test_page_numbers_upright_on_rotated_pages(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 3)
    with pymupdf.open(src) as doc:
        doc[1].set_rotation(90)
        doc.save(tmp_path / "mixed.pdf")
    out = tmp_path / "numbered.pdf"
    AddPageNumbers().convert(tmp_path / "mixed.pdf", out, noop, {"style": "Page {n} of {total}", "start": 1})
    with pymupdf.open(out) as doc:
        for index, page in enumerate(doc, start=1):
            assert f"Page {index} of 3" in page.get_text()
            for block in page.get_text("dict")["blocks"]:
                for line in block["lines"]:
                    if line["spans"][0]["text"].endswith("of 3"):
                        dx, dy = pymupdf.Point(line["dir"]) * pymupdf.Matrix(page.rotation)
                        assert (round(dx), round(dy)) == (1, 0)  # reads left to right as displayed
                        bottom = pymupdf.Rect(line["bbox"]) * page.rotation_matrix
                        assert bottom.y0 > page.rect.height * 0.8  # bottom of the page as displayed


def test_page_numbers_start_and_subset(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 4)
    AddPageNumbers().convert(src, tmp_path / "n.pdf", noop, {"style": "{n}", "start": 10, "pages": "3-"})
    texts = page_texts(tmp_path / "n.pdf")
    assert texts[0] == "Page 1"
    assert texts[2].endswith("10") and texts[3].endswith("11")


def test_watermark(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 2)
    out = tmp_path / "wm.pdf"
    AddWatermark().convert(src, out, noop, {"text": "DRAFT", "layout": "diagonal", "opacity": 0.25})
    assert all("DRAFT" in t for t in page_texts(out))
    with pytest.raises(ConversionError, match="Latin"):
        AddWatermark().convert(src, tmp_path / "x.pdf", noop, {"text": "গোপনীয়"})
    with pytest.raises(ConversionError, match="text"):
        AddWatermark().convert(src, tmp_path / "y.pdf", noop, {"text": "  "})


# ---- images -----------------------------------------------------------------


def make_image(path, size=(400, 300), mode="RGB", color=(200, 30, 30)):
    Image.new(mode, size, color).save(path)
    return path


def test_images_to_one_pdf_landscape_on_a4(tmp_path):
    jpg = make_image(tmp_path / "wide.jpg")
    png = make_image(tmp_path / "tall.png", size=(300, 400), mode="RGBA", color=(0, 0, 255, 128))
    out = tmp_path / "photos.pdf"
    ImagesToPdf().combine([jpg, png], out, noop, {"page_size": "a4", "margin": 36})
    with pymupdf.open(out) as doc:
        assert doc.page_count == 2
        assert round(doc[0].rect.width) == 842  # landscape image, landscape page
        assert round(doc[1].rect.width) == 595
        assert doc[0].get_images()


def test_image_exif_rotation_is_respected(tmp_path):
    path = tmp_path / "phone.jpg"
    image = Image.new("RGB", (400, 200), (10, 120, 10))
    exif = image.getexif()
    exif[0x0112] = 6  # stored sideways, display rotated 90°
    image.save(path, exif=exif)
    out = tmp_path / "phone.pdf"
    ImagesToPdf().convert(path, out, noop, {"page_size": "fit", "margin": 0})
    with pymupdf.open(out) as doc:
        assert doc[0].rect.height > doc[0].rect.width


def test_heic_to_pdf(tmp_path):
    pillow_heif = pytest.importorskip("pillow_heif")
    path = tmp_path / "photo.heic"
    pillow_heif.register_heif_opener()
    Image.new("RGB", (64, 48), (90, 90, 200)).save(path, format="HEIF")
    ImagesToPdf().convert(path, tmp_path / "photo.pdf", noop, {})
    with pymupdf.open(tmp_path / "photo.pdf") as doc:
        assert doc[0].get_images()


def test_pdf_to_jpg_and_png(tmp_path):
    src = numbered_pdf(tmp_path / "doc.pdf", 3)
    PdfToJpg().convert(src, tmp_path / "jpg", noop, {"dpi": 72, "pages": ""})
    assert sorted(p.name for p in (tmp_path / "jpg").iterdir()) == [f"doc page {n}.jpg" for n in (1, 2, 3)]
    PdfToPng().convert(src, tmp_path / "png", noop, {"dpi": 150, "pages": "2"})
    (png,) = (tmp_path / "png").iterdir()
    assert png.name == "doc page 2.png"
    width, height = Image.open(png).size
    assert width == 1240 and abs(height - 1754) <= 1  # A4 at 150 dpi


def test_extract_images(tmp_path):
    src = tmp_path / "pics.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    for x, color in ((72, (255, 0, 0)), (300, (0, 0, 255))):
        image = tmp_path / f"{color}.png"
        make_image(image, size=(80, 60), color=color)
        page.insert_image(pymupdf.Rect(x, 72, x + 160, 192), filename=str(image))
    doc.save(src)
    out = tmp_path / "pics (images)"
    note = ExtractImages().convert(src, out, noop)
    assert note == "2 image(s)"
    assert len(list(out.iterdir())) == 2
    with pytest.raises(ConversionError, match="No images"):
        ExtractImages().convert(numbered_pdf(tmp_path / "plain.pdf", 1), tmp_path / "none", noop)
    assert not (tmp_path / "none").exists()


# ---- registry ---------------------------------------------------------------


def test_every_tool_is_registered_once():
    registry = default_registry()
    keys = [a.key for a in registry.actions()]
    assert len(keys) == len(set(keys)) == 17
    groups = []
    for action in registry.actions():
        if action.group not in groups:
            groups.append(action.group)
    assert groups == ["Convert", "Organize pages", "Optimize", "Edit", "Security"]
