from file_converter.converters.base import (
    EXCEL,
    IMAGE_INPUTS,
    SUPPORTED_INPUTS,
    WORD,
    Action,
    ConversionError,
    Converter,
    ConverterRegistry,
    Option,
    Options,
    OutputFormat,
    output_path_for,
)


def default_registry() -> ConverterRegistry:
    """The registry the app uses. The order here is the order of the tools in the window."""
    from file_converter.converters.images import ExtractImages, ImagesToPdf, PdfToJpg, PdfToPng
    from file_converter.converters.pdf_edit import AddPageNumbers, AddWatermark, CompressPdf, FlattenPdf
    from file_converter.converters.pdf_pages import ExtractPages, MergePdfs, RemovePages, RotatePages, SplitPdf
    from file_converter.converters.pdf_security import ProtectPdf, UnlockPdf
    from file_converter.converters.pdf_to_excel import PdfToExcel
    from file_converter.converters.pdf_to_word import PdfToWord

    registry = ConverterRegistry()
    for converter in (
        # Convert
        PdfToWord(),
        PdfToExcel(),
        ImagesToPdf(),
        PdfToJpg(),
        PdfToPng(),
        ExtractImages(),
        # Organize pages
        MergePdfs(),
        SplitPdf(),
        ExtractPages(),
        RemovePages(),
        RotatePages(),
        # Optimize
        CompressPdf(),
        FlattenPdf(),
        # Edit
        AddPageNumbers(),
        AddWatermark(),
        # Security
        ProtectPdf(),
        UnlockPdf(),
    ):
        registry.register(converter)
    return registry


__all__ = [
    "EXCEL",
    "IMAGE_INPUTS",
    "SUPPORTED_INPUTS",
    "WORD",
    "Action",
    "ConversionError",
    "Converter",
    "ConverterRegistry",
    "Option",
    "Options",
    "OutputFormat",
    "default_registry",
    "output_path_for",
]
