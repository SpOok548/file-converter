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
    return ConverterRegistry()


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
