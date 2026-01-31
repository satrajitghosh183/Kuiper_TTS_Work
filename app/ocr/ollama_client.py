"""
Ollama OCR client for local Vision Language Model inference.

This client uses Ollama for completely local, API-free inference.
Supports various vision models like LLaVA, BakLLaVA, and more.
"""

from __future__ import annotations

import base64
import io
import os
from typing import Optional

import structlog
from PIL import Image

from app.exceptions import ConfigurationError, OCRError
from app.ocr.base import BaseOCRClient

logger = structlog.get_logger()


# Recommended Ollama models for different use cases
OLLAMA_VISION_MODELS = {
    "general": "llava:13b",          # Good balance of quality and speed
    "fast": "llava:7b",              # Faster, lighter model
    "quality": "llava:34b",          # Highest quality, needs more VRAM
    "bakllava": "bakllava",          # BakLLaVA - good for documents
    "llava-llama3": "llava-llama3",  # LLaVA with Llama 3 base
    "minicpm-v": "minicpm-v",        # MiniCPM-V - efficient vision model
    "moondream": "moondream",        # Lightweight vision model
}


class OllamaOCRClient(BaseOCRClient):
    """
    Client for Ollama-based local vision model inference.

    Supports any Ollama vision model for completely offline, API-free
    PDF to LaTeX conversion.

    Example:
        >>> client = OllamaOCRClient(model="llava:13b")
        >>> image = Image.open("page.png")
        >>> latex = client.ocr_image(image, output_format="latex")

    Note:
        Requires Ollama to be installed and running locally.
        Install from: https://ollama.ai/download
    """

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3,
        num_ctx: int = 8192,
        temperature: float = 0.1,
    ):
        """
        Initialize the Ollama OCR client.

        Args:
            model: Ollama model name (e.g., "llava:13b", "bakllava").
                   Defaults to "llava:13b".
            host: Ollama server URL. Defaults to http://localhost:11434
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            num_ctx: Context window size for generation.
            temperature: Sampling temperature (lower = more deterministic).

        Raises:
            ConfigurationError: If Ollama is not available.
        """
        self.model = model or OLLAMA_VISION_MODELS["general"]
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.timeout = timeout
        self.max_retries = max_retries
        self.num_ctx = num_ctx
        self.temperature = temperature
        
        self._client = None
        self._init_client()

        logger.info(
            "Initialized Ollama OCR client",
            model=self.model,
            host=self.host,
            timeout=self.timeout,
        )

    def _init_client(self) -> None:
        """Initialize the Ollama client."""
        try:
            import ollama
            self._ollama = ollama
            
            # Try to connect and verify
            client = ollama.Client(host=self.host)
            self._client = client
            
        except ImportError:
            raise ConfigurationError(
                message="Ollama Python package not installed. "
                "Install with: pip install ollama",
                details={"missing_package": "ollama"},
            )
        except Exception as e:
            logger.warning(
                "Could not connect to Ollama server",
                host=self.host,
                error=str(e),
            )
            # Don't raise here - we'll check availability later

    def _encode_image(self, image: Image.Image) -> str:
        """
        Convert PIL Image to base64 string.

        Args:
            image: PIL Image object

        Returns:
            Base64-encoded image string
        """
        buffer = io.BytesIO()
        # Convert to RGB if necessary (handles RGBA, P modes)
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")
        image.save(buffer, format="PNG", optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def ocr_image(
        self,
        image: Image.Image,
        prompt: Optional[str] = None,
        output_format: str = "latex",
    ) -> str:
        """
        Perform OCR on an image using Ollama vision model.

        Args:
            image: PIL Image object
            prompt: Custom prompt (uses default if None)
            output_format: "latex", "markdown", or "plain"

        Returns:
            Extracted text in specified format

        Raises:
            OCRError: If OCR processing fails
        """
        if prompt is None:
            prompt = self.get_default_prompt(output_format)

        image_b64 = self._encode_image(image)

        # Retry logic
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self._client.chat(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                            "images": [image_b64],
                        }
                    ],
                    options={
                        "num_ctx": self.num_ctx,
                        "temperature": self.temperature,
                    },
                )

                content = response["message"]["content"]
                logger.debug(
                    "OCR completed successfully",
                    model=self.model,
                    output_length=len(content),
                )
                return content

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for model not found
                if "not found" in error_str or "pull" in error_str:
                    raise OCRError(
                        message=f"Model '{self.model}' not found. "
                        f"Pull it with: ollama pull {self.model}",
                        details={"model": self.model},
                    )

                # Retry on transient errors
                if attempt < self.max_retries - 1:
                    import time
                    wait_time = 2 ** attempt
                    logger.warning(
                        "OCR request failed, retrying",
                        attempt=attempt + 1,
                        error=str(e),
                        wait_time=wait_time,
                    )
                    time.sleep(wait_time)
                    continue

        raise OCRError(
            message=f"OCR failed after {self.max_retries} attempts: {last_error}",
            details={"model": self.model, "last_error": str(last_error)},
        )

    def is_available(self) -> bool:
        """
        Check if Ollama is available and the model is ready.

        Returns:
            True if Ollama is running and model is available
        """
        if self._client is None:
            return False
            
        try:
            # Check if server is responding
            models = self._client.list()
            
            # Check if our model is available
            model_names = [m.get("name", "") for m in models.get("models", [])]
            
            # Handle model name variations (with/without tag)
            model_base = self.model.split(":")[0]
            for name in model_names:
                if name.startswith(model_base):
                    return True
                    
            logger.warning(
                "Model not found locally",
                model=self.model,
                available=model_names,
                hint=f"Run: ollama pull {self.model}",
            )
            return False
            
        except Exception as e:
            logger.warning("Ollama availability check failed", error=str(e))
            return False

    def pull_model(self) -> bool:
        """
        Pull/download the model if not available locally.

        Returns:
            True if model is now available
        """
        try:
            logger.info("Pulling model from Ollama", model=self.model)
            self._client.pull(self.model)
            logger.info("Model pulled successfully", model=self.model)
            return True
        except Exception as e:
            logger.error("Failed to pull model", model=self.model, error=str(e))
            return False

    def list_models(self) -> list:
        """
        List available Ollama models.

        Returns:
            List of model names
        """
        try:
            models = self._client.list()
            return [m.get("name", "") for m in models.get("models", [])]
        except Exception:
            return []

    def switch_model(self, model: str) -> None:
        """
        Switch to a different Ollama model.

        Args:
            model: New model name to use
        """
        self.model = model
        logger.info("Switched Ollama model", model=model)

    @staticmethod
    def get_recommended_models() -> dict:
        """
        Get dictionary of recommended models for different use cases.

        Returns:
            Dictionary mapping use case to model name
        """
        return OLLAMA_VISION_MODELS.copy()
