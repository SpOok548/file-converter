"""Add or remove a PDF password."""

from __future__ import annotations

from pathlib import Path

from file_converter.converters.base import (
    PASSWORD,
    Action,
    ConversionError,
    Converter,
    Option,
    Options,
    ProgressCallback,
)
from file_converter.converters.pdf_common import has_encryption, open_pdf, save_pdf

GROUP = "Security"

PROTECT = Action(
    "protect",
    "Protect with password",
    ".pdf",
    group=GROUP,
    suffix=" (protected)",
    description="Saves a copy that needs the password to open (AES-256 encryption).",
    options=(Option("password", "Password", PASSWORD, default="", required=True),),
)
UNLOCK = Action(
    "unlock",
    "Remove password",
    ".pdf",
    group=GROUP,
    suffix=" (unlocked)",
    description="Saves a copy without the password. You need to know the current password.",
    options=(Option("password", "Current password", PASSWORD, default="", required=True),),
)

PDF = frozenset({".pdf"})


class ProtectPdf(Converter):
    input_extensions = PDF
    output_format = PROTECT

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        password = (options or {}).get("password") or ""
        if not password:
            raise ConversionError("Type a password first.")
        doc = open_pdf(source)
        with doc:
            if has_encryption(doc):
                raise ConversionError("This PDF already has a password. Remove it first, then add a new one.")
            progress(0.3)
            save_pdf(
                doc,
                destination,
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw=password,
                owner_pw=password,
                permissions=-1,
            )
        progress(1.0)
        return None


class UnlockPdf(Converter):
    input_extensions = PDF
    output_format = UNLOCK

    def convert(self, source: Path, destination: Path, progress: ProgressCallback, options: Options | None = None):
        import pymupdf

        password = (options or {}).get("password") or ""
        if not password:
            raise ConversionError("Type the PDF's current password first.")
        try:
            doc = pymupdf.open(source)
        except Exception as exc:  # noqa: BLE001
            raise ConversionError("This file couldn't be opened as a PDF. It may be damaged.") from exc
        with doc:
            if not doc.is_pdf:
                raise ConversionError("This file isn't a PDF.")
            if not has_encryption(doc):
                raise ConversionError("This PDF doesn't have a password.")
            # Also checked for PDFs with only a permissions password, which open without one,
            # so a wrong password is reported instead of silently ignored.
            if not doc.authenticate(password):
                raise ConversionError("That password is wrong for this PDF.")
            progress(0.3)
            save_pdf(doc, destination, encryption=pymupdf.PDF_ENCRYPT_NONE)
        progress(1.0)
        return None
