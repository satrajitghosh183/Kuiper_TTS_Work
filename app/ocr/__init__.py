"""
OCR module for PDF-to-LaTeX conversion.

Provides multiple OCR backends:
- HuggingFaceOCRClient: Cloud-based inference via HF Inference API
- LocalHuggingFaceOCR: Local GPU inference using Transformers
"""

from app.ocr.hf_client import HuggingFaceOCRClient
from app.ocr.local_client import LocalHuggingFaceOCR
from app.ocr.base import BaseOCRClient

__all__ = ["HuggingFaceOCRClient", "LocalHuggingFaceOCR", "BaseOCRClient"]

