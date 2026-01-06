"""
Local Hugging Face OCR client using Transformers.

This client runs inference locally using GPU, which is faster for
batch processing and doesn't have API rate limits.
"""

from __future__ import annotations

import os
from typing import Optional

import structlog
from PIL import Image

from app.config import RECOMMENDED_MODELS
from app.exceptions import ConfigurationError, OCRError
from app.ocr.base import BaseOCRClient

logger = structlog.get_logger()


class LocalHuggingFaceOCR(BaseOCRClient):
    """
    Local inference using Hugging Face Transformers.

    Requires GPU for reasonable performance. Supports various VLM models
    optimized for document understanding.

    Example:
        >>> client = LocalHuggingFaceOCR(model_id="nanonets/Nanonets-OCR-s")
        >>> image = Image.open("page.png")
        >>> latex = client.process_page(image)

    Note:
        This requires the 'local' extras: pip install pdf-to-latex[local]
    """

    def __init__(
        self,
        model_id: Optional[str] = None,
        device: str = "cuda",
        torch_dtype: Optional[str] = "bfloat16",
        use_flash_attention: bool = True,
        max_new_tokens: int = 8192,
    ):
        """
        Initialize the local OCR client.

        Args:
            model_id: Hugging Face model ID
            device: Device to run on ("cuda", "cpu", or "auto")
            torch_dtype: Data type for model weights
            use_flash_attention: Whether to use Flash Attention 2
            max_new_tokens: Maximum tokens to generate

        Raises:
            ConfigurationError: If required packages are not installed
        """
        self.model_id = model_id or RECOMMENDED_MODELS["equations"]
        self.device = device
        self.max_new_tokens = max_new_tokens
        self._model = None
        self._processor = None

        # Lazy import to avoid dependency issues
        try:
            import torch
            from transformers import AutoModelForImageTextToText, AutoProcessor

            self._torch = torch
            self._AutoProcessor = AutoProcessor
            self._AutoModel = AutoModelForImageTextToText
        except ImportError as e:
            raise ConfigurationError(
                message="Local inference requires transformers and torch. "
                "Install with: pip install pdf-to-latex[local]",
                details={"missing_package": str(e)},
            )

        # Determine torch dtype
        if torch_dtype == "bfloat16":
            self._dtype = torch.bfloat16
        elif torch_dtype == "float16":
            self._dtype = torch.float16
        else:
            self._dtype = torch.float32

        # Attention implementation
        self._attn_impl = "flash_attention_2" if use_flash_attention else "eager"

        logger.info(
            "Initialized local HuggingFace OCR client",
            model_id=self.model_id,
            device=self.device,
            dtype=torch_dtype,
        )

    def _load_model(self) -> None:
        """Load model and processor (lazy loading)."""
        if self._model is not None:
            return

        logger.info("Loading model", model_id=self.model_id)

        try:
            self._processor = self._AutoProcessor.from_pretrained(self.model_id)

            self._model = self._AutoModel.from_pretrained(
                self.model_id,
                torch_dtype=self._dtype,
                device_map=self.device,
                attn_implementation=self._attn_impl,
            )
            self._model.eval()

            logger.info("Model loaded successfully", model_id=self.model_id)

        except Exception as e:
            logger.error("Failed to load model", model_id=self.model_id, error=str(e))
            raise OCRError(
                message=f"Failed to load model: {e}",
                details={"model_id": self.model_id},
            )

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
        """
        return self.process_page(image, prompt, output_format)

    def process_page(
        self,
        image: Image.Image,
        prompt: Optional[str] = None,
        output_format: str = "latex",
    ) -> str:
        """
        Process a single page image.

        Args:
            image: PIL Image object
            prompt: Custom prompt (uses default if None)
            output_format: Output format ("latex", "markdown", "plain")

        Returns:
            Extracted content in specified format
        """
        self._load_model()

        if prompt is None:
            prompt = self.get_default_prompt(output_format)

        # Convert image to RGB if necessary
        if image.mode in ("RGBA", "P", "LA"):
            image = image.convert("RGB")

        messages = [
            {
                "role": "system",
                "content": "You are a precise document-to-LaTeX converter.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            },
        ]

        try:
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )

            inputs = self._processor(
                text=[text], images=[image], padding=True, return_tensors="pt"
            ).to(self.device)

            with self._torch.no_grad():
                output_ids = self._model.generate(
                    **inputs,
                    max_new_tokens=self.max_new_tokens,
                    do_sample=False,
                    temperature=0.1,
                )

            # Extract only the generated tokens
            generated_ids = [
                out[len(inp) :]
                for inp, out in zip(inputs.input_ids, output_ids)
            ]

            result = self._processor.batch_decode(
                generated_ids, skip_special_tokens=True
            )[0]

            logger.debug("Page processed successfully", output_length=len(result))
            return result

        except Exception as e:
            logger.error("Failed to process page", error=str(e))
            raise OCRError(
                message=f"Failed to process page: {e}",
                details={"model_id": self.model_id},
            )

    def is_available(self) -> bool:
        """
        Check if the OCR client is available and properly configured.

        Returns:
            True if GPU is available and model can be loaded
        """
        try:
            import torch

            if self.device == "cuda":
                return torch.cuda.is_available()
            return True
        except ImportError:
            return False

    def get_memory_usage(self) -> dict:
        """
        Get current GPU memory usage.

        Returns:
            Dictionary with memory statistics
        """
        try:
            import torch

            if torch.cuda.is_available():
                return {
                    "allocated_gb": torch.cuda.memory_allocated() / 1e9,
                    "reserved_gb": torch.cuda.memory_reserved() / 1e9,
                    "max_allocated_gb": torch.cuda.max_memory_allocated() / 1e9,
                }
        except Exception:
            pass
        return {}

    def unload_model(self) -> None:
        """Unload model from memory to free GPU resources."""
        if self._model is not None:
            del self._model
            self._model = None

        if self._processor is not None:
            del self._processor
            self._processor = None

        # Clear CUDA cache
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Model unloaded and CUDA cache cleared")
        except Exception:
            pass

