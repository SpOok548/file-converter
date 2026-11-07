"""Optimize and edit: compress, page numbers, watermark, flatten."""

from __future__ import annotations

import math
from pathlib import Path

from file_converter.converters.base import (
    CHOICE,
    NUMBER,
    PAGES,
    TEXT,
    Action,
    ConversionError,
    Converter,
    Option,
    Options,
    ProgressCallback,
    file_size_note,
)
from file_converter.converters.pdf_common import open_pdf, parse_pages, save_pdf

COMPRESS = Action(
    "compress",
    "Compress PDF",
    ".pdf",
    group="Optimize",
    suffix=" (compressed)",
    description="Makes the file smaller by shrinking large pictures and removing unused data.",
    options=(
        Option(
            "level",
            "Compression",
            CHOICE,
            default="medium",
            choices=(
                ("Light (best quality)", "light"),
                ("Recommended", "medium"),
                ("Strong (smallest file)", "strong"),
            ),
        ),
    ),
)
FLATTEN = Action(
    "flatten",
    "Flatten forms and comments",
    ".pdf",
    group="Optimize",
    suffix=" (flattened)",
    description="Turns filled-in form fields, comments and stamps into a normal part of the page so they can't be changed.",
)

_PAGES_ALL = Option("pages", "Pages", PAGES, default="", placeholder="blank = all pages")

PAGE_NUMBERS = Action(
    "page-numbers",
    "Add page numbers",
    ".pdf",
    group="Edit",
    suffix=" (numbered)",
    description="Prints a page number on each page.",
    options=(
        Option(
            "position",
            "Position",
            CHOICE,
            default="bottom-center",
            choices=(
                ("Bottom centre", "bottom-center"),
                ("Bottom right", "bottom-right"),
                ("Bottom left", "bottom-left"),
                ("Top centre", "top-center"),
                ("Top right", "top-right"),
                ("Top left", "top-left"),
            ),
        ),
        Option(
            "style",
            "Style",
            CHOICE,
            default="{n}",
            choices=(("1", "{n}"), ("Page 1", "Page {n}"), ("Page 1 of 9", "Page {n} of {total}"), ("1 / 9", "{n} / {total}")),
        ),
        Option("start", "First number", NUMBER, default=1, minimum=0, maximum=99999),
        Option("size", "Text size", CHOICE, default=11, choices=(("Small", 9), ("Medium", 11), ("Large", 14))),
        _PAGES_ALL,
    ),
)
WATERMARK = Action(
    "watermark",
    "Add watermark",
    ".pdf",
    group="Edit",
    suffix=" (watermarked)",
    description="Stamps see-through text, such as CONFIDENTIAL or DRAFT, across each page.",
    options=(
        Option("text", "Text", TEXT, default="CONFIDENTIAL", required=True),
        Option("layout", "Layout", CHOICE, default="diagonal", choices=(("Diagonal", "diagonal"), ("Straight", "straight"))),
        Option(
            "opacity",
            "Strength",
            CHOICE,
            default=0.25,
            choices=(("Light", 0.12), ("Medium", 0.25), ("Strong", 0.45)),
        ),
        _PAGES_ALL,
    ),
)

PDF = frozenset({".pdf"})
FONT = "helv"
EDGE = 28  # distance of page numbers from the page edge, in points


def _check_latin(text: str) -> None:
    try:
        text.encode("latin-1")
    except UnicodeEncodeError:
        raise ConversionError(
            "For now the text can only use Latin letters, digits and common symbols."
        ) from None


def _put_text(page, start, text: str, size: float, color, opacity: float = 1.0, angle: float = 0, pivot=None):
    """Write text at a point given as the reader sees the page, upright even on rotated pages."""
    import pymupdf

    derotate = page.derotation_matrix
    point = pymupdf.Point(start) * derotate
    morph = (pymupdf.Point(pivot) * derotate, pymupdf.Matrix(angle)) if angle else None
    page.insert_text(
        point,
        text,
        fontsize=size,
        fontname=FONT,
        color=color,
        fill_opacity=opacity,
        rotate=page.rotation,
        morph=morph,
    )


class CompressPdf(Converter):
    input_extensions = PDF
    output_format = COMPRESS

    # (shrink pictures above this many dots per inch, down to this many, JPEG quality)
    LEVELS = {"light": (220, 200, 85), "medium": (160, 150, 75), "strong": (110, 96, 60)}

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        level = (options or {}).get("level") or "medium"
        threshold, target, quality = self.LEVELS.get(level, self.LEVELS["medium"])
        before = source.stat().st_size
        doc = open_pdf(source)
        with doc:
            progress(0.1)
            try:
                doc.rewrite_images(dpi_threshold=threshold, dpi_target=target, quality=quality)
            except Exception:  # noqa: BLE001 - unusual images: still compact the rest of the file
                pass
            progress(0.7)
            save_pdf(doc, destination, use_objstms=1)
        after = destination.stat().st_size
        if after >= before:
            destination.unlink(missing_ok=True)
            raise ConversionError(
                "This PDF is already as small as this setting can make it, so no new file was saved. "
                "Try \"Strong\" for a smaller file."
                if level != "strong"
                else "This PDF is already as small as it can get, so no new file was saved."
            )
        progress(1.0)
        return file_size_note(before, after)


class FlattenPdf(Converter):
    input_extensions = PDF
    output_format = FLATTEN

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        doc = open_pdf(source)
        with doc:
            fields = sum(1 for page in doc for _ in page.widgets())
            notes = sum(1 for page in doc for a in page.annots() if a.type[1] not in ("Link", "Popup"))
            if not fields and not notes:
                raise ConversionError("This PDF has no form fields or comments to flatten.")
            progress(0.3)
            try:
                doc.bake(annots=True, widgets=True)
            except Exception as exc:  # noqa: BLE001
                raise ConversionError(f"Couldn't flatten this PDF: {exc}") from exc
            save_pdf(doc, destination)
        progress(1.0)
        parts = []
        if fields:
            parts.append(f"{fields} form field(s)")
        if notes:
            parts.append(f"{notes} comment(s)")
        return " and ".join(parts) + " flattened"


class AddPageNumbers(Converter):
    input_extensions = PDF
    output_format = PAGE_NUMBERS

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        options = {**PAGE_NUMBERS.default_options(), **(options or {})}
        style = str(options["style"])
        size = float(options["size"])
        start = int(options["start"])
        vertical, horizontal = str(options["position"]).split("-")
        doc = open_pdf(source)
        with doc:
            pages = parse_pages(options.get("pages"), doc.page_count)
            total = start + len(pages) - 1
            for index, number in enumerate(pages):
                page = doc[number]
                label = style.format(n=start + index, total=total)
                width = pymupdf.get_text_length(label, fontname=FONT, fontsize=size)
                area = page.rect
                x = {"left": EDGE, "center": (area.width - width) / 2, "right": area.width - EDGE - width}[horizontal]
                y = EDGE + size if vertical == "top" else area.height - EDGE
                _put_text(page, (x, y), label, size, color=(0, 0, 0))
                progress(0.9 * (index + 1) / len(pages))
            save_pdf(doc, destination)
        progress(1.0)
        return f"{len(pages)} page(s) numbered"


class AddWatermark(Converter):
    input_extensions = PDF
    output_format = WATERMARK

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        options = {**WATERMARK.default_options(), **(options or {})}
        text = " ".join(str(options.get("text") or "").split())
        if not text:
            raise ConversionError("Type the watermark text first.")
        _check_latin(text)
        diagonal = options["layout"] == "diagonal"
        opacity = float(options["opacity"])
        doc = open_pdf(source)
        with doc:
            pages = parse_pages(options.get("pages"), doc.page_count)
            for index, number in enumerate(pages):
                page = doc[number]
                area = page.rect
                span = math.hypot(area.width, area.height) if diagonal else area.width
                size = min(96.0, 0.7 * span / pymupdf.get_text_length(text, fontname=FONT, fontsize=1))
                width = pymupdf.get_text_length(text, fontname=FONT, fontsize=size)
                centre = (area.width / 2, area.height / 2)
                start = (centre[0] - width / 2, centre[1] + size * 0.35)
                angle = math.degrees(math.atan2(area.height, area.width)) if diagonal else 0
                _put_text(page, start, text, size, color=(0.5, 0.5, 0.5), opacity=opacity, angle=angle, pivot=centre)
                progress(0.9 * (index + 1) / len(pages))
            save_pdf(doc, destination)
        progress(1.0)
        return None
