"""Images to PDF, PDF pages to images, and pulling images out of a PDF."""

from __future__ import annotations

import io
from pathlib import Path

from file_converter.converters.base import (
    BOOL,
    CHOICE,
    IMAGE_INPUTS,
    PAGES,
    Action,
    ConversionError,
    Converter,
    Option,
    Options,
    ProgressCallback,
)
from file_converter.converters.pdf_common import open_pdf, parse_pages, save_pdf

A4 = (595.0, 842.0)
LETTER = (612.0, 792.0)

IMAGES_TO_PDF = Action(
    "images-pdf",
    "PDF (.pdf) from images",
    ".pdf",
    description="Turns photos and scans into PDF pages. Tick \"Combine\" to put them all in one PDF, in list order.",
    combine="combine",
    options=(
        Option("combine", "Combine into one PDF", BOOL, default=True),
        Option(
            "page_size",
            "Page size",
            CHOICE,
            default="a4",
            choices=(("A4", "a4"), ("US Letter", "letter"), ("Same as image", "fit")),
        ),
        Option(
            "margin",
            "Margin",
            CHOICE,
            default=0,
            choices=(("None", 0), ("Small (0.5 in)", 36), ("Large (1 in)", 72)),
        ),
    ),
)

_RESOLUTIONS = (("Screen (72 dpi)", 72), ("Standard (150 dpi)", 150), ("Print (300 dpi)", 300))

PDF_TO_JPG = Action(
    "jpg",
    "JPG images (one per page)",
    "",
    suffix=" (jpg)",
    description="Saves each page as a JPG picture in a new folder.",
    options=(
        Option("dpi", "Quality", CHOICE, default=150, choices=_RESOLUTIONS),
        Option("pages", "Pages", PAGES, default="", placeholder="blank = all pages"),
    ),
)
PDF_TO_PNG = Action(
    "png",
    "PNG images (one per page)",
    "",
    suffix=" (png)",
    description="Saves each page as a PNG picture in a new folder. PNG is sharper for text, JPG is smaller for photos.",
    options=PDF_TO_JPG.options,
)
EXTRACT_IMAGES = Action(
    "extract-images",
    "Extract images from PDF",
    "",
    suffix=" (images)",
    description="Saves the pictures embedded in each PDF, at their original quality, in a new folder.",
)

MIN_IMAGE_SIDE = 16  # skip tiny decorations (bullets, lines, spacer pixels)


def _load_image(source: Path):
    """Open any supported image upright, as Pillow sees it."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    if source.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError as exc:  # pragma: no cover - only if the optional wheel is missing
            raise ConversionError("HEIC support isn't installed.") from exc
    try:
        image = Image.open(source)
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ConversionError(f"{source.name} couldn't be opened as an image. It may be damaged.") from exc
    return image, ImageOps.exif_transpose(image)


def _image_bytes(source: Path) -> tuple[bytes, int, int]:
    """The image data to place in the PDF. JPEGs are copied untouched so no quality is lost."""
    original, upright = _load_image(source)
    width, height = upright.size
    if original.format == "JPEG" and original.getexif().get(0x0112, 1) == 1:
        return source.read_bytes(), width, height
    image = upright
    buffer = io.BytesIO()
    if image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info):
        image.convert("RGBA").save(buffer, "PNG")
    elif original.format == "JPEG":
        image.convert("RGB").save(buffer, "JPEG", quality=95)
    else:
        if image.mode not in ("RGB", "L", "1"):
            image = image.convert("RGB")
        image.save(buffer, "PNG")
    return buffer.getvalue(), width, height


def _add_image_page(doc, source: Path, options: Options) -> None:
    import pymupdf

    data, width, height = _image_bytes(source)
    margin = float(options.get("margin") or 0)
    size = options.get("page_size") or "a4"
    if size == "fit":
        page_w, page_h = width * 72 / 96 + 2 * margin, height * 72 / 96 + 2 * margin
    else:
        page_w, page_h = A4 if size == "a4" else LETTER
        if width > height:  # landscape photo on a landscape page
            page_w, page_h = page_h, page_w
    page = doc.new_page(width=page_w, height=page_h)
    area = pymupdf.Rect(margin, margin, page_w - margin, page_h - margin)
    try:
        page.insert_image(area, stream=data, keep_proportion=True)
    except Exception as exc:  # noqa: BLE001
        raise ConversionError(f"Couldn't place {source.name} in the PDF: {exc}") from exc


class ImagesToPdf(Converter):
    input_extensions = frozenset(IMAGE_INPUTS)
    output_format = IMAGES_TO_PDF

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        return self.combine([source], destination, progress, options)

    def combine(self, sources: list[Path], destination: Path, progress: ProgressCallback, options=None):
        import pymupdf

        options = {**IMAGES_TO_PDF.default_options(), **(options or {})}
        doc = pymupdf.open()
        with doc:
            for index, source in enumerate(sources, start=1):
                _add_image_page(doc, source, options)
                progress(0.9 * index / len(sources))
            save_pdf(doc, destination)
        progress(1.0)
        return f"{len(sources)} page(s)" if len(sources) > 1 else None


class _PdfToImages(Converter):
    input_extensions = frozenset({".pdf"})
    image_format = "png"

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        options = {**self.output_format.default_options(), **(options or {})}
        dpi = int(options.get("dpi") or 150)
        doc = open_pdf(source)
        with doc:
            pages = parse_pages(options.get("pages"), doc.page_count)
            destination.mkdir(parents=True)
            digits = len(str(doc.page_count))
            for index, number in enumerate(pages, start=1):
                pix = doc[number].get_pixmap(dpi=dpi, alpha=False)
                name = destination / f"{source.stem} page {number + 1:0{digits}d}.{self.image_format}"
                if self.image_format == "jpg":
                    pix.save(name, jpg_quality=90)
                else:
                    pix.save(name)
                progress(index / len(pages))
        return f"{len(pages)} image(s)"


class PdfToJpg(_PdfToImages):
    output_format = PDF_TO_JPG
    image_format = "jpg"


class PdfToPng(_PdfToImages):
    output_format = PDF_TO_PNG
    image_format = "png"


class ExtractImages(Converter):
    input_extensions = frozenset({".pdf"})
    output_format = EXTRACT_IMAGES

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        doc = open_pdf(source)
        saved = 0
        seen: set[int] = set()
        with doc:
            for page_index, page in enumerate(doc):
                for info in page.get_images(full=True):
                    xref, smask = info[0], info[1]
                    if xref in seen:
                        continue
                    seen.add(xref)
                    try:
                        extracted = doc.extract_image(xref)
                    except Exception:  # noqa: BLE001 - skip images MuPDF can't decode
                        continue
                    if not extracted or min(extracted["width"], extracted["height"]) < MIN_IMAGE_SIDE:
                        continue
                    if not saved:
                        destination.mkdir(parents=True)
                    saved += 1
                    stem = destination / f"{source.stem} p{page_index + 1} image {saved}"
                    if smask:  # transparent image: combine colour and mask into a PNG
                        try:
                            pix = pymupdf.Pixmap(pymupdf.Pixmap(doc, xref), pymupdf.Pixmap(doc, smask))
                            if pix.n - pix.alpha > 3:
                                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                            pix.save(f"{stem}.png")
                            continue
                        except Exception:  # noqa: BLE001 - fall back to the colour part alone
                            pass
                    Path(f"{stem}.{extracted['ext']}").write_bytes(extracted["image"])
                progress((page_index + 1) / doc.page_count)
        if not saved:
            raise ConversionError("No images were found in this PDF.")
        return f"{saved} image(s)"
