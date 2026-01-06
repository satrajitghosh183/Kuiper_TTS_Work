# Kuiper TTS Core Module
# Shared utilities and constants for the Kuiper TTS training pipeline

import os
import re
import math
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

# Constants
SAMPLE_RATE = 22050
DEFAULT_BATCH_SIZE = 64
VOICE_NAME = "kuiper"

# Default paths (can be overridden by config)
DEFAULT_ROOT_DIR = Path("./data")
DEFAULT_AUDIO_DIR = DEFAULT_ROOT_DIR / "wavs"
DEFAULT_CACHE_DIR = DEFAULT_ROOT_DIR / "cache"
DEFAULT_RECORDINGS_DIR = Path("./recordings")
DEFAULT_CONFIG_PATH = DEFAULT_ROOT_DIR / "kuiper.json"
DEFAULT_LOG_DIR = DEFAULT_ROOT_DIR / "training_outputs"


@dataclass
class KuiperConfig:
    """Configuration for Kuiper TTS training."""
    
    voice_name: str = VOICE_NAME
    sample_rate: int = SAMPLE_RATE
    espeak_voice: str = "en-us"
    batch_size: int = DEFAULT_BATCH_SIZE
    
    # Paths
    root_dir: Path = DEFAULT_ROOT_DIR
    audio_dir: Path = DEFAULT_AUDIO_DIR
    cache_dir: Path = DEFAULT_CACHE_DIR
    recordings_dir: Path = DEFAULT_RECORDINGS_DIR
    config_path: Path = DEFAULT_CONFIG_PATH
    log_dir: Path = DEFAULT_LOG_DIR
    checkpoint_path: Optional[Path] = None
    
    # Microphone settings
    microphone_device_id: Optional[int] = None
    microphone_gain: float = 1.0
    normalize_audio: bool = True
    silence_threshold: float = 0.01
    
    def __post_init__(self):
        """Convert string paths to Path objects."""
        if isinstance(self.root_dir, str):
            self.root_dir = Path(self.root_dir)
        if isinstance(self.audio_dir, str):
            self.audio_dir = Path(self.audio_dir)
        if isinstance(self.cache_dir, str):
            self.cache_dir = Path(self.cache_dir)
        if isinstance(self.recordings_dir, str):
            self.recordings_dir = Path(self.recordings_dir)
        if isinstance(self.config_path, str):
            self.config_path = Path(self.config_path)
        if isinstance(self.log_dir, str):
            self.log_dir = Path(self.log_dir)
        if isinstance(self.checkpoint_path, str):
            self.checkpoint_path = Path(self.checkpoint_path)


def fix_padding(filename: str) -> str:
    """
    Fix padding in audio filenames to ensure 4-digit numbering.
    
    Args:
        filename: Original filename (e.g., "1.wav" or "phoneme_0001.wav")
    
    Returns:
        Filename with proper 4-digit padding (e.g., "0001.wav")
    """
    match = re.search(r'\d+', str(filename))
    if match:
        return f"{int(match.group()):04d}.wav"
    return str(filename)


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
    
    Returns:
        Formatted string (e.g., "2h 30m", "45m", "30s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        if minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"


def round_to_power_of_2(n: int) -> int:
    """
    Round down to nearest power of 2.
    
    Args:
        n: Input number
    
    Returns:
        Nearest power of 2 less than or equal to n
    """
    if n <= 0:
        return 1
    return 2 ** int(math.log2(n))


__all__ = [
    # Constants
    "SAMPLE_RATE",
    "DEFAULT_BATCH_SIZE",
    "VOICE_NAME",
    # Config
    "KuiperConfig",
    # Utilities
    "fix_padding",
    "format_duration",
    "round_to_power_of_2",
]

# Lazy imports to avoid circular dependencies
def __getattr__(name):
    if name == "SystemAnalyzer":
        from .system_analyzer import SystemAnalyzer
        return SystemAnalyzer
    elif name == "SystemReport":
        from .system_analyzer import SystemReport
        return SystemReport
    elif name == "AudioProcessor":
        from .audio_processor import AudioProcessor
        return AudioProcessor
    elif name == "AudioInfo":
        from .audio_processor import AudioInfo
        return AudioInfo
    elif name == "DataPreparer":
        from .data_preparer import DataPreparer
        return DataPreparer
    elif name == "RecordingInfo":
        from .data_preparer import RecordingInfo
        return RecordingInfo
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

