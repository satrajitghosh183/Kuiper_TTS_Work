# Configuration Management
# Handles environment variables and production settings

import os
import logging
from pathlib import Path
from typing import Optional, List
try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        raise ImportError(
            "pydantic-settings is required. Install it with: pip install pydantic-settings"
        )
from pydantic import Field, validator
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Server Configuration
    host: str = Field(default="127.0.0.1", env="KUIPER_HOST")
    port: int = Field(default=8765, env="KUIPER_PORT")
    reload: bool = Field(default=False, env="KUIPER_RELOAD")
    
    # Environment
    environment: str = Field(default="development", env="KUIPER_ENV")
    debug: bool = Field(default=False, env="KUIPER_DEBUG")
    
    # Security
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        env="KUIPER_CORS_ORIGINS"
    )
    max_upload_size_mb: int = Field(default=100, env="KUIPER_MAX_UPLOAD_SIZE_MB")
    rate_limit_per_minute: int = Field(default=60, env="KUIPER_RATE_LIMIT")
    
    # Paths
    project_root: Optional[Path] = Field(default=None, env="KUIPER_PROJECT_ROOT")
    recordings_dir: Optional[Path] = Field(default=None, env="KUIPER_RECORDINGS_DIR")
    data_dir: Optional[Path] = Field(default=None, env="KUIPER_DATA_DIR")
    
    # Logging
    log_level: str = Field(default="INFO", env="KUIPER_LOG_LEVEL")
    log_file: Optional[Path] = Field(default=None, env="KUIPER_LOG_FILE")
    
    # Training
    default_batch_size: int = Field(default=64, env="KUIPER_DEFAULT_BATCH_SIZE")
    max_epochs: int = Field(default=2000, env="KUIPER_MAX_EPOCHS")
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("project_root", "recordings_dir", "data_dir", "log_file", pre=True)
    def parse_paths(cls, v):
        if v is None or v == "":
            return None
        return Path(v) if isinstance(v, str) else v
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() == "development"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def get_project_root() -> Path:
    """Get the project root directory."""
    settings = get_settings()
    if settings.project_root:
        return settings.project_root
    
    # Default: parent of backend directory
    backend_dir = Path(__file__).parent.parent
    return backend_dir.parent


def get_recordings_dir() -> Path:
    """Get the recordings directory."""
    settings = get_settings()
    if settings.recordings_dir:
        return settings.recordings_dir
    
    project_root = get_project_root()
    return project_root / "recordings"


def get_data_dir() -> Path:
    """Get the data directory."""
    settings = get_settings()
    if settings.data_dir:
        return settings.data_dir
    
    project_root = get_project_root()
    return project_root / "data"
