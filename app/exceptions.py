"""
Custom exceptions for PDF-to-LaTeX conversion system.
"""

from __future__ import annotations

from typing import Optional


class PDFToLaTeXError(Exception):
    """Base exception for all PDF-to-LaTeX errors."""

    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} - Details: {self.details}"
        return self.message


class ConversionError(PDFToLaTeXError):
    """Error during the conversion process."""

    pass


class OCRError(PDFToLaTeXError):
    """Error during OCR/VLM processing."""

    pass


class PDFParseError(PDFToLaTeXError):
    """Error parsing the PDF document."""

    pass


class LaTeXValidationError(PDFToLaTeXError):
    """Error validating generated LaTeX."""

    pass


class ImageExtractionError(PDFToLaTeXError):
    """Error extracting images from PDF."""

    pass


class APIError(PDFToLaTeXError):
    """Error communicating with external API."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        super().__init__(message, details)
        self.provider = provider
        self.status_code = status_code


class RateLimitError(APIError):
    """Rate limit exceeded for API."""

    pass


class AuthenticationError(APIError):
    """Authentication failed for API."""

    pass


class ModelNotFoundError(APIError):
    """Requested model not found."""

    pass


class TimeoutError(PDFToLaTeXError):
    """Operation timed out."""

    pass


class FileError(PDFToLaTeXError):
    """File-related error."""

    pass


class FileTooLargeError(FileError):
    """File exceeds size limit."""

    pass


class UnsupportedFileTypeError(FileError):
    """File type not supported."""

    pass


class ConfigurationError(PDFToLaTeXError):
    """Configuration error."""

    pass

