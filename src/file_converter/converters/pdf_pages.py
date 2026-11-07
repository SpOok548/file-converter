"""Organize pages: merge, split, extract, remove and rotate."""

from __future__ import annotations

from pathlib import Path

from file_converter.converters.base import (
    CHOICE,
    PAGES,
    Action,
    ConversionError,
    Converter,
    Option,
    Options,
    ProgressCallback,
)
from file_converter.converters.pdf_common import (
    describe_pages,
    open_pdf,
    page_groups,
    parse_pages,
    save_pdf,
)

GROUP = "Organize pages"

MERGE = Action(
    "merge",
    "Merge PDFs into one",
    ".pdf",
    group=GROUP,
    suffix=" (merged)",
    combine=True,
    description="Joins every PDF in the list into one file, in list order. Use Move up / Move down to reorder.",
)
SPLIT = Action(
    "split",
    "Split PDF",
    "",
    group=GROUP,
    suffix=" (split)",
    description="Saves pages as separate PDFs in a new folder.",
    options=(
        Option(
            "ranges",
            "Split into",
            PAGES,
            default="",
            placeholder="blank = one file per page, or e.g. 1-3, 4-10, 11-",
        ),
    ),
)
EXTRACT = Action(
    "extract",
    "Extract pages",
    ".pdf",
    group=GROUP,
    suffix=" (extract)",
    description="Copies the chosen pages into a new PDF, in the order you type them.",
    options=(Option("pages", "Pages", PAGES, default="", required=True, placeholder="e.g. 1-3, 5, 8-"),),
)
REMOVE = Action(
    "remove",
    "Remove pages",
    ".pdf",
    group=GROUP,
    suffix=" (pages removed)",
    description="Saves a copy of the PDF without the chosen pages.",
    options=(Option("pages", "Pages to remove", PAGES, default="", required=True, placeholder="e.g. 2, 5-6"),),
)
ROTATE = Action(
    "rotate",
    "Rotate pages",
    ".pdf",
    group=GROUP,
    suffix=" (rotated)",
    description="Turns pages a quarter or half turn.",
    options=(
        Option(
            "angle",
            "Rotate",
            CHOICE,
            default=90,
            choices=(("90° clockwise", 90), ("180°", 180), ("90° counter-clockwise", 270)),
        ),
        Option("pages", "Pages", PAGES, default="", placeholder="blank = all pages"),
    ),
)

PDF = frozenset({".pdf"})


class MergePdfs(Converter):
    input_extensions = PDF
    output_format = MERGE

    def combine(self, sources: list[Path], destination: Path, progress: ProgressCallback, options=None):
        import pymupdf

        if len(sources) < 2:
            raise ConversionError("Add at least two PDFs to merge.")
        result = pymupdf.open()
        try:
            for index, source in enumerate(sources, start=1):
                doc = open_pdf(source)
                with doc:
                    try:
                        result.insert_pdf(doc)
                    except Exception as exc:  # noqa: BLE001
                        raise ConversionError(f"Couldn't add {source.name}: {exc}") from exc
                progress(0.9 * index / len(sources))
            pages = result.page_count
            save_pdf(result, destination)
        finally:
            result.close()
        progress(1.0)
        return f"{len(sources)} files, {pages} pages"


class SplitPdf(Converter):
    input_extensions = PDF
    output_format = SPLIT

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        options = options or {}
        doc = open_pdf(source)
        with doc:
            groups = page_groups(options.get("ranges"), doc.page_count)
            destination.mkdir(parents=True)
            for index, pages in enumerate(groups, start=1):
                part = pymupdf.open()
                with part:
                    for page in pages:
                        part.insert_pdf(doc, from_page=page, to_page=page)
                    save_pdf(part, destination / f"{source.stem} p{describe_pages(pages)}.pdf")
                progress(index / len(groups))
        return f"{len(groups)} files"


class ExtractPages(Converter):
    input_extensions = PDF
    output_format = EXTRACT

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        doc = open_pdf(source)
        with doc:
            pages = parse_pages((options or {}).get("pages"), doc.page_count)
            doc.select(pages)
            progress(0.5)
            save_pdf(doc, destination)
        progress(1.0)
        return f"{len(pages)} page(s)"


class RemovePages(Converter):
    input_extensions = PDF
    output_format = REMOVE

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        doc = open_pdf(source)
        with doc:
            remove = set(parse_pages((options or {}).get("pages"), doc.page_count))
            keep = [i for i in range(doc.page_count) if i not in remove]
            if not keep:
                raise ConversionError("That would remove every page. Leave at least one page.")
            doc.select(keep)
            progress(0.5)
            save_pdf(doc, destination)
        progress(1.0)
        return f"{len(remove)} page(s) removed, {len(keep)} left"


class RotatePages(Converter):
    input_extensions = PDF
    output_format = ROTATE

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        options = options or {}
        angle = int(options.get("angle") or 90)
        doc = open_pdf(source)
        with doc:
            pages = parse_pages(options.get("pages"), doc.page_count)
            for index, number in enumerate(pages, start=1):
                page = doc[number]
                page.set_rotation((page.rotation + angle) % 360)
                progress(0.8 * index / len(pages))
            save_pdf(doc, destination)
        progress(1.0)
        return f"{len(pages)} page(s) rotated"
