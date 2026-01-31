"""
OCR module for PDF-to-LaTeX conversion.

Provides multiple OCR backends:
- HuggingFaceOCRClient: Cloud-based inference via HF Inference API
- LocalHuggingFaceOCR: Local GPU inference using Transformers
- OllamaOCRClient: Completely local inference via Ollama (no API needed)
"""

from app.ocr.hf_client import HuggingFaceOCRClient
from app.ocr.local_client import LocalHuggingFaceOCR
from app.ocr.ollama_client import OllamaOCRClient
from app.ocr.base import BaseOCRClient

__all__ = [
    "HuggingFaceOCRClient",
    "LocalHuggingFaceOCR",
    "OllamaOCRClient",
    "BaseOCRClient",
]

