"""
Pytest fixtures and configuration.
"""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

# Set test environment variables before importing app modules
os.environ.setdefault("HF_TOKEN", "test_token")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("API_KEY", "test_api_key")


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_image() -> Image.Image:
    """Create a sample image for testing."""
    # Create a simple test image
    img = Image.new("RGB", (800, 600), color="white")
    return img


@pytest.fixture
def sample_pdf_bytes(temp_dir: Path) -> bytes:
    """Create a simple PDF for testing."""
    try:
        import fitz

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Test PDF Document", fontsize=24)
        page.insert_text((72, 120), "This is a test paragraph.")
        page.insert_text((72, 150), "$E = mc^2$")  # Math equation

        pdf_path = temp_dir / "test.pdf"
        doc.save(str(pdf_path))
        doc.close()

        return pdf_path.read_bytes()
    except ImportError:
        # Return minimal valid PDF if PyMuPDF not available
        return b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj xref 0 4 0000000000 65535 f\n0000000009 00000 n\n0000000052 00000 n\n0000000101 00000 n\ntrailer<</Size 4/Root 1 0 R>>startxref 172 %%EOF"


@pytest.fixture
def mock_ocr_client():
    """Create a mock OCR client."""
    mock = MagicMock()
    mock.ocr_image.return_value = """\\section{Introduction}

This is a test document with some mathematical content.

\\begin{equation}
E = mc^2
\\end{equation}

This demonstrates the PDF to LaTeX conversion."""
    mock.is_available.return_value = True
    return mock


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock = MagicMock()
    mock.hgetall.return_value = {
        "status": "completed",
        "progress": "100",
        "result_path": "/app/outputs/test.tex",
    }
    mock.hset.return_value = True
    mock.ping.return_value = True
    return mock


@pytest.fixture
def test_client():
    """Create a FastAPI test client."""
    from app.main import app

    return TestClient(app)


@pytest.fixture
def conversion_config():
    """Create a test conversion configuration."""
    from app.config import ConversionConfig

    return ConversionConfig(
        extract_images=False,
        hf_use_inference_api=True,
        hf_model_id="test-model",
        hf_api_token="test_token",
    )

