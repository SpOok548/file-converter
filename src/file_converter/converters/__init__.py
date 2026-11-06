from file_converter.converters.base import (
    EXCEL,
    OUTPUT_FORMATS,
    SUPPORTED_INPUTS,
    WORD,
    ConversionError,
    Converter,
    ConverterRegistry,
    OutputFormat,
    output_path_for,
)


def default_registry() -> ConverterRegistry:
    """The registry the app uses. Real converters are registered here as they are added."""
    from file_converter.converters.pdf_to_excel import PdfToExcel
    from file_converter.converters.pdf_to_word import PdfToWord

    registry = ConverterRegistry()
    registry.register(PdfToWord())
    registry.register(PdfToExcel())
    return registry


__all__ = [
    "EXCEL",
    "OUTPUT_FORMATS",
    "SUPPORTED_INPUTS",
    "WORD",
    "ConversionError",
    "Converter",
    "ConverterRegistry",
    "OutputFormat",
    "default_registry",
    "output_path_for",
]
