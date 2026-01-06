"""
Tests for configuration module.
"""

import os
from unittest.mock import patch

import pytest

from app.config import ConversionConfig, ParserType, Settings, RECOMMENDED_MODELS


class TestConversionConfig:
    """Tests for ConversionConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = ConversionConfig()

        assert config.parser_type == "AUTO"
        assert config.extract_images is True
        assert config.image_format == "png"
        assert config.dpi == 200
        assert config.document_class == "article"
        assert config.primary_provider == "huggingface"

    def test_custom_values(self):
        """Test custom configuration values."""
        config = ConversionConfig(
            extract_images=False,
            dpi=300,
            document_class="report",
            hf_model_id="custom-model",
        )

        assert config.extract_images is False
        assert config.dpi == 300
        assert config.document_class == "report"
        assert config.hf_model_id == "custom-model"

    def test_packages_default(self):
        """Test default packages list."""
        config = ConversionConfig()

        assert "amsmath" in config.use_packages
        assert "graphicx" in config.use_packages
        assert "booktabs" in config.use_packages

    def test_hf_token_from_env(self):
        """Test HF token loaded from environment."""
        with patch.dict(os.environ, {"HF_TOKEN": "test_env_token"}):
            config = ConversionConfig()
            assert config.hf_api_token == "test_env_token"


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self):
        """Test default settings values."""
        with patch.dict(os.environ, {}, clear=False):
            settings = Settings()

            assert settings.MAX_FILE_SIZE_MB == 50
            assert settings.RATE_LIMIT_PER_MINUTE == 30
            assert settings.LOG_LEVEL == "INFO"

    def test_settings_from_env(self):
        """Test settings loaded from environment."""
        env_vars = {
            "MAX_FILE_SIZE_MB": "100",
            "RATE_LIMIT_PER_MINUTE": "60",
            "LOG_LEVEL": "DEBUG",
            "HF_MODEL_ID": "custom/model",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            settings = Settings()

            assert settings.MAX_FILE_SIZE_MB == 100
            assert settings.RATE_LIMIT_PER_MINUTE == 60
            assert settings.LOG_LEVEL == "DEBUG"
            assert settings.HF_MODEL_ID == "custom/model"


class TestRecommendedModels:
    """Tests for recommended models dictionary."""

    def test_models_exist(self):
        """Test that recommended models are defined."""
        assert "general" in RECOMMENDED_MODELS
        assert "equations" in RECOMMENDED_MODELS
        assert "fast" in RECOMMENDED_MODELS

    def test_model_ids_are_strings(self):
        """Test that all model IDs are strings."""
        for task, model_id in RECOMMENDED_MODELS.items():
            assert isinstance(model_id, str)
            assert "/" in model_id or len(model_id) > 0

