"""
Hugging Face Inference API client for document OCR.

This client uses the Hugging Face Inference API for cloud-based
Vision Language Model inference, eliminating the need for local GPU.
"""

from __future__ import annotations

import base64
import io
import os
import time
from typing import Optional

import structlog
from huggingface_hub import InferenceClient
from PIL import Image

from app.config import RECOMMENDED_MODELS
from app.exceptions import APIError, AuthenticationError, RateLimitError
from app.ocr.base import BaseOCRClient

logger = structlog.get_logger()


class HuggingFaceOCRClient(BaseOCRClient):
    """
    Client for Hugging Face Inference API for document OCR.

    Supports multiple models optimized for document understanding:
    - Qwen/Qwen2.5-VL-7B-Instruct (recommended for general docs)
    - nanonets/Nanonets-OCR-s (excellent for LaTeX equations)
    - stepfun-ai/GOT-OCR2_0 (good for formatted text)
    - reducto/RolmOCR (fast, lightweight)

    Example:
        >>> client = HuggingFaceOCRClient(model_id="Qwen/Qwen2.5-VL-7B-Instruct")
        >>> image = Image.open("page.png")
        >>> latex = client.ocr_image(image, output_format="latex")
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        token: Optional[str] = None,
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        """
        Initialize the Hugging Face OCR client.

        Args:
            model_id: Hugging Face model ID. Defaults to recommended general model.
            token: HF API token. If None, reads from HF_TOKEN env var.
            timeout: Request timeout in seconds.
            max_retries: Maximum number of retry attempts.
            retry_delay: Base delay between retries (exponential backoff).

        Raises:
            AuthenticationError: If no token is provided or found.
        """
        self.token = token or os.environ.get("HF_TOKEN")
        if not self.token:
            raise AuthenticationError(
                message="Hugging Face API token required. "
                "Set HF_TOKEN environment variable or pass token parameter.",
                provider="huggingface",
            )

        self.model_id = model_id or RECOMMENDED_MODELS["general"]
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self.client = InferenceClient(token=self.token)

        logger.info(
            "Initialized HuggingFace OCR client",
            model_id=self.model_id,
            timeout=self.timeout,
        )

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
        Perform OCR on an image and return structured output.

        Args:
            image: PIL Image object
            prompt: Custom prompt (uses default if None)
            output_format: "latex", "markdown", or "plain"

        Returns:
            Extracted text in specified format

        Raises:
            OCRError: If OCR processing fails
            RateLimitError: If rate limit is exceeded
        """
        if prompt is None:
            prompt = self.get_default_prompt(output_format)

        image_b64 = self._encode_image(image)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        # Retry logic with exponential backoff
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_id,
                    messages=messages,
                    max_tokens=8192,
                    temperature=0.1,  # Low temperature for accuracy
                )

                content = response.choices[0].message.content
                logger.debug(
                    "OCR completed successfully",
                    model=self.model_id,
                    output_length=len(content),
                )
                return content

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limiting
                if "rate" in error_str or "429" in error_str:
                    if attempt < self.max_retries - 1:
                        wait_time = self.retry_delay * (2**attempt)
                        logger.warning(
                            "Rate limited, retrying",
                            attempt=attempt + 1,
                            wait_time=wait_time,
                        )
                        time.sleep(wait_time)
                        continue
                    raise RateLimitError(
                        message="Rate limit exceeded",
                        provider="huggingface",
                        status_code=429,
                    )

                # Check for authentication errors
                if "401" in error_str or "unauthorized" in error_str:
                    raise AuthenticationError(
                        message="Invalid Hugging Face API token",
                        provider="huggingface",
                        status_code=401,
                    )

                # Retry on transient errors
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    logger.warning(
                        "OCR request failed, retrying",
                        attempt=attempt + 1,
                        error=str(e),
                        wait_time=wait_time,
                    )
                    time.sleep(wait_time)
                    continue

        raise APIError(
            message=f"OCR failed after {self.max_retries} attempts: {last_error}",
            provider="huggingface",
            details={"model_id": self.model_id, "last_error": str(last_error)},
        )

    def is_available(self) -> bool:
        """
        Check if the OCR client is available and properly configured.

        Returns:
            True if client is ready to use
        """
        return bool(self.token)

    def switch_model(self, model_id: str) -> None:
        """
        Switch to a different model.

        Args:
            model_id: New model ID to use
        """
        self.model_id = model_id
        logger.info("Switched OCR model", model_id=model_id)

    def get_model_for_task(self, task: str) -> str:
        """
        Get recommended model for a specific task.

        Args:
            task: One of "general", "equations", "tables", "formatted", "fast"

        Returns:
            Recommended model ID
        """
        return RECOMMENDED_MODELS.get(task, RECOMMENDED_MODELS["general"])

