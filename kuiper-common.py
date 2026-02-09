# kuiper_common.py
# Shared utilities and constants for TTS training

import os
import re
import math
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('kuiper')

# Constants
SAMPLE_RATE = 22050
DEFAULT_BATCH_SIZE = 64
VOICE_NAME = "kuiper"

# Get the project root directory (where this file is located)
PROJECT_ROOT = Path(__file__).parent.resolve()

# Default paths - use absolute paths based on project root
DEFAULT_ROOT_DIR = PROJECT_ROOT / "data"
DEFAULT_AUDIO_DIR = DEFAULT_ROOT_DIR / "wavs"
DEFAULT_CACHE_DIR = DEFAULT_ROOT_DIR / "cache"
DEFAULT_RECORDINGS_DIR = PROJECT_ROOT / "recordings"
DEFAULT_CONFIG_PATH = DEFAULT_ROOT_DIR / f"{VOICE_NAME}.json"
DEFAULT_LOG_DIR = DEFAULT_ROOT_DIR / "training_outputs"
DEFAULT_CHECKPOINT_PATH = DEFAULT_ROOT_DIR / "starting.ckpt"

# Legacy aliases for backward compatibility
ROOT_DIR = DEFAULT_ROOT_DIR
AUDIO_DIR = DEFAULT_AUDIO_DIR
DRIVE_LOG_DIR = DEFAULT_LOG_DIR
CONFIG_PATH = DEFAULT_CONFIG_PATH
CLEANED_CKPT = DEFAULT_CHECKPOINT_PATH
CACHE_DIR = DEFAULT_CACHE_DIR


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
    checkpoint_path: Optional[Path] = DEFAULT_CHECKPOINT_PATH
  
    # Microphone settings
    microphone_device_id: Optional[int] = None
    microphone_gain: float = 1.0
    normalize_audio: bool = True
    silence_threshold: float = 0.01
    
    def __post_init__(self):
        """Convert string paths to Path objects and ensure absolute paths."""
        path_attrs = ['root_dir', 'audio_dir', 'cache_dir', 'recordings_dir', 
                     'config_path', 'log_dir', 'checkpoint_path']
        
        for attr in path_attrs:
            value = getattr(self, attr)
            if value is not None:
                if isinstance(value, str):
                    value = Path(value)
                # Make relative paths absolute based on project root
                if not value.is_absolute():
                    value = PROJECT_ROOT / value
                setattr(self, attr, value)


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


def get_gpu_memory() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Get total, free, and allocated GPU memory in GB using PyTorch."""
    try:
        import torch
        if not torch.cuda.is_available():
            return None, None, None
        
        device = torch.cuda.current_device()
        total_memory = torch.cuda.get_device_properties(device).total_memory / (1024**3)
        allocated = torch.cuda.memory_allocated(device) / (1024**3)
        reserved = torch.cuda.memory_reserved(device) / (1024**3)
        free_memory = total_memory - reserved
        
        return total_memory, free_memory, allocated
    except Exception as e:
        logger.warning(f"Failed to get GPU memory via PyTorch: {e}")
        return None, None, None


def get_gpu_memory_nvidia_smi() -> Tuple[Optional[float], Optional[float]]:
    """Fallback: Get GPU memory using nvidia-smi."""
    import subprocess
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.total,memory.free', '--format=csv,nounits,noheader'],
            capture_output=True, text=True, check=True, timeout=10
        )
        lines = result.stdout.strip().split('\n')
        if lines:
            total, free = map(int, lines[0].split(','))
            return total / 1024, free / 1024  # Convert MB to GB
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.debug(f"nvidia-smi not available: {e}")
    return None, None


def get_mps_memory() -> Tuple[Optional[float], Optional[float]]:
    """Get Apple Silicon GPU memory (unified memory)."""
    import platform
    import subprocess
    
    if platform.system() != "Darwin":
        return None, None
    
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"],
            capture_output=True, text=True, check=True, timeout=5
        )
        total_bytes = int(result.stdout.strip())
        total_gb = total_bytes / (1024 ** 3)
        # Estimate GPU portion (Apple Silicon shares memory)
        gpu_mem_gb = total_gb * 0.75
        return gpu_mem_gb, gpu_mem_gb * 0.8  # Estimate free
    except Exception as e:
        logger.debug(f"Failed to get MPS memory: {e}")
        return None, None


def calculate_optimal_batch_size(
    total_gpu_memory_gb: float, 
    memory_per_batch_gb: float = 0.8,
    safety_margin: float = 0.15
) -> int:
    """
    Calculate optimal batch size based on GPU memory.
    
    Args:
        total_gpu_memory_gb: Total GPU memory in GB
        memory_per_batch_gb: Memory used per batch in GB (default 0.8 for TTS)
        safety_margin: Fraction of memory to reserve (default 0.15 = 15%)
    
    Returns:
        Optimal batch size (int, power of 2)
    """
    if memory_per_batch_gb <= 0:
        return DEFAULT_BATCH_SIZE
    
    available_memory = total_gpu_memory_gb * (1 - safety_margin)
    optimal_batch = int(available_memory / memory_per_batch_gb)
    
    # Round down to nearest power of 2 for efficiency
    if optimal_batch > 0:
        optimal_batch = round_to_power_of_2(optimal_batch)
    
    # Clamp to reasonable range
    return max(4, min(128, optimal_batch))


def auto_detect_batch_size() -> int:
    """
    Auto-detect optimal batch size based on available GPU/hardware.
    
    Returns:
        Optimal batch size for training
    """
    # Try CUDA first
    total_mem, free_mem, allocated = get_gpu_memory()
    
    if total_mem is not None:
        logger.info(f"📊 CUDA GPU Memory: {total_mem:.2f} GB total, {free_mem:.2f} GB free")
        optimal = calculate_optimal_batch_size(total_mem)
        logger.info(f"🎯 Calculated optimal batch size: {optimal}")
        return optimal
    
    # Try nvidia-smi fallback
    total_mem, free_mem = get_gpu_memory_nvidia_smi()
    if total_mem is not None:
        logger.info(f"📊 GPU Memory (nvidia-smi): {total_mem:.2f} GB total, {free_mem:.2f} GB free")
        optimal = calculate_optimal_batch_size(total_mem)
        logger.info(f"🎯 Calculated optimal batch size: {optimal}")
        return optimal
    
    # Try Apple Silicon MPS
    total_mem, free_mem = get_mps_memory()
    if total_mem is not None:
        logger.info(f"📊 Apple Silicon Memory: {total_mem:.2f} GB GPU accessible")
        # MPS is slower, use smaller batches
        optimal = calculate_optimal_batch_size(total_mem, memory_per_batch_gb=1.2)
        logger.info(f"🎯 Calculated optimal batch size (MPS): {optimal}")
        return optimal
    
    logger.warning("⚠️  No GPU detected, using default batch size for CPU")
    return 8  # Small batch for CPU training


def ensure_directories():
    """Create all necessary directories if they don't exist."""
    dirs = [DEFAULT_ROOT_DIR, DEFAULT_AUDIO_DIR, DEFAULT_CACHE_DIR, 
            DEFAULT_RECORDINGS_DIR, DEFAULT_LOG_DIR]
    
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {dir_path}")


def validate_setup() -> Tuple[bool, list]:
    """
    Validate that the training setup is correct.
    
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    # Check if data directory exists
    if not DEFAULT_ROOT_DIR.exists():
        errors.append(f"Data directory not found: {DEFAULT_ROOT_DIR}")
    
    # Check for metadata file
    metadata_path = DEFAULT_ROOT_DIR / "metadata.csv"
    if not metadata_path.exists():
        errors.append(f"Metadata file not found: {metadata_path}")
    
    # Check for audio files
    if DEFAULT_AUDIO_DIR.exists():
        wav_files = list(DEFAULT_AUDIO_DIR.glob("*.wav"))
        if len(wav_files) == 0:
            errors.append(f"No WAV files found in: {DEFAULT_AUDIO_DIR}")
        else:
            logger.info(f"Found {len(wav_files)} WAV files")
    else:
        errors.append(f"Audio directory not found: {DEFAULT_AUDIO_DIR}")
    
    # Check for checkpoint (optional warning)
    if DEFAULT_CHECKPOINT_PATH and not DEFAULT_CHECKPOINT_PATH.exists():
        logger.warning(f"Pre-trained checkpoint not found: {DEFAULT_CHECKPOINT_PATH}")
        logger.warning("Training will start from scratch")
    
    return len(errors) == 0, errors


# Export all public functions and classes
__all__ = [
    # Constants
    "SAMPLE_RATE",
    "DEFAULT_BATCH_SIZE", 
    "VOICE_NAME",
    "PROJECT_ROOT",
    # Paths
    "DEFAULT_ROOT_DIR",
    "DEFAULT_AUDIO_DIR",
    "DEFAULT_CACHE_DIR",
    "DEFAULT_RECORDINGS_DIR",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_LOG_DIR",
    "DEFAULT_CHECKPOINT_PATH",
    # Legacy aliases
    "ROOT_DIR",
    "AUDIO_DIR",
    "DRIVE_LOG_DIR",
    "CONFIG_PATH",
    "CLEANED_CKPT",
    "CACHE_DIR",
    # Config
    "KuiperConfig",
    # Utilities
    "fix_padding",
    "format_duration",
    "round_to_power_of_2",
    "get_gpu_memory",
    "get_gpu_memory_nvidia_smi",
    "get_mps_memory",
    "calculate_optimal_batch_size",
    "auto_detect_batch_size",
    "ensure_directories",
    "validate_setup",
    "logger",
]
