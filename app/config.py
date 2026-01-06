"""
Configuration management for PDF-to-LaTeX conversion system.

Supports environment variables, .env files, and programmatic configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class ParserType(str, Enum):
    """Parser type selection for document processing."""

    LLM_PARSE = "llm"
    STATIC_PARSE = "static"
    AUTO = "auto"


class Provider(str, Enum):
    """Supported AI providers."""

    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    GOOGLE = "google"


@dataclass
class ConversionConfig:
    """
    Configuration for PDF-to-LaTeX conversion.

    This dataclass holds all settings for the conversion pipeline,
    including parser settings, image handling, and LaTeX output options.
    """

    # Parser settings
    parser_type: Literal["LLM_PARSE", "STATIC_PARSE", "AUTO"] = "AUTO"

    # Image handling (TOGGLEABLE FEATURE)
    extract_images: bool = True  # Master toggle for image extraction
    image_output_dir: str = "./figures"  # Where to save extracted images
    image_format: str = "png"  # png, jpg, pdf
    generate_image_captions: bool = True  # Use VLM to generate captions
    inline_images_as_base64: bool = False  # Embed images or reference files

    # Processing settings
    pages_per_split: int = 4  # Pages per processing chunk
    max_threads: int = 4  # Parallel processing threads
    dpi: int = 200  # PDF rendering resolution

    # LaTeX output settings
    document_class: str = "article"  # article, report, book, etc.
    use_packages: List[str] = field(
        default_factory=lambda: [
            "amsmath",
            "amssymb",
            "graphicx",
            "hyperref",
            "geometry",
            "booktabs",
            "longtable",
            "xcolor",
            "float",
        ]
    )
    preserve_formatting: bool = True

    # API Configuration
    primary_provider: str = "huggingface"  # huggingface, openai, google
    fallback_provider: str = "google"

    # Hugging Face specific
    hf_model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct"
    hf_use_inference_api: bool = True  # Use HF Inference API vs local
    hf_api_token: Optional[str] = None  # Set via HF_TOKEN env var

    # Timeouts and retries
    request_timeout: int = 120
    max_retries: int = 3
    retry_delay: int = 5

    def __post_init__(self):
        """Load API token from environment if not provided."""
        if self.hf_api_token is None:
            self.hf_api_token = os.environ.get("HF_TOKEN")


class Settings(BaseSettings):
    """
    Application settings with environment variable support.

    This class is used for the production FastAPI server configuration.
    Settings can be overridden via environment variables or .env file.
    """

    # API Settings
    API_KEY: str = Field(default="", description="API key for authentication")
    ALLOWED_ORIGINS: List[str] = Field(
        default=["*"], description="CORS allowed origins"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(default=30, description="Rate limit per minute")
    MAX_FILE_SIZE_MB: int = Field(default=50, description="Maximum file size in MB")

    # Hugging Face Configuration
    HF_TOKEN: str = Field(default="", description="Hugging Face API token")
    HF_MODEL_ID: str = Field(
        default="Qwen/Qwen2.5-VL-7B-Instruct",
        description="Hugging Face model ID for OCR",
    )
    HF_USE_INFERENCE_API: bool = Field(
        default=True, description="Use HF Inference API vs local"
    )

    # Fallback providers
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key (fallback)")
    GOOGLE_API_KEY: str = Field(default="", description="Google API key (fallback)")

    # Redis/Celery Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379", description="Redis URL")
    CELERY_BROKER_URL: str = Field(
        default="redis://localhost:6379/0", description="Celery broker URL"
    )
    CELERY_RESULT_BACKEND: str = Field(
        default="redis://localhost:6379/1", description="Celery result backend URL"
    )

    # Storage Paths
    UPLOAD_DIR: str = Field(default="./uploads", description="Upload directory")
    OUTPUT_DIR: str = Field(default="./outputs", description="Output directory")
    FIGURES_DIR: str = Field(default="./figures", description="Figures directory")

    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # LaTeX Settings
    DEFAULT_DOCUMENT_CLASS: str = Field(
        default="article", description="Default LaTeX document class"
    )
    DPI: int = Field(default=200, description="PDF rendering DPI")

    # Processing
    MAX_WORKERS: int = Field(default=4, description="Maximum worker threads")
    TASK_TIMEOUT: int = Field(default=600, description="Task timeout in seconds")

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, v):
        """Parse origins from string or list."""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        return v

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Returns:
        Settings: Application settings
    """
    return Settings()


# Convenience accessor
settings = get_settings()


# Recommended models for different use cases
RECOMMENDED_MODELS = {
    "general": "Qwen/Qwen2.5-VL-7B-Instruct",
    "equations": "nanonets/Nanonets-OCR-s",
    "tables": "microsoft/table-transformer-detection",
    "formatted": "stepfun-ai/GOT-OCR2_0",
    "fast": "reducto/RolmOCR",
}

