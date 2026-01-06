# kuiper_common.py
# Shared configuration, utilities, and GPU helpers for Kuiper TTS

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import torch

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

def setup_logging(level: str = "INFO", json: bool = False) -> None:
    """Configure root logger."""
    root = logging.getLogger()
    if root.handlers:
        return  # already configured

    log_level = getattr(logging, level.upper(), logging.INFO)
    root.setLevel(log_level)

    handler = logging.StreamHandler()
    if json:
        import json as _json

        class JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                payload = {
                    "level": record.levelname,
                    "name": record.name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    payload["exc_info"] = self.formatException(record.exc_info)
                return _json.dumps(payload)

        handler.setFormatter(JsonFormatter())
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)

    root.addHandler(handler)


def get_logger(name: Optional[str] = None) -> logging.Logger:
    return logging.getLogger(name or __name__)


# -----------------------------------------------------------------------------
# Paths & configuration
# -----------------------------------------------------------------------------

# Resolve paths relative to this repo by default, override via env vars.
PROJECT_ROOT = Path(__file__).resolve().parent

DATA_ROOT = Path(os.environ.get("KUIPER_DATA_ROOT", PROJECT_ROOT / "data")).resolve()
VOICE_NAME = os.environ.get("KUIPER_VOICE_NAME", "kuiper")
SAMPLE_RATE = int(os.environ.get("KUIPER_SAMPLE_RATE", "22050"))
AUDIO_DIR = Path(os.environ.get("KUIPER_AUDIO_DIR", DATA_ROOT / "wavs")).resolve()
DRIVE_LOG_DIR = Path(os.environ.get("KUIPER_TRAIN_LOG_DIR", DATA_ROOT / "training_outputs")).resolve()
CONFIG_PATH = Path(os.environ.get("KUIPER_CONFIG_PATH", DATA_ROOT / f"{VOICE_NAME}.json")).resolve()
CLEANED_CKPT = Path(os.environ.get("KUIPER_CLEANED_CKPT", DATA_ROOT / "starting.ckpt")).resolve()
CACHE_DIR = Path(os.environ.get("KUIPER_CACHE_DIR", DATA_ROOT / "cache")).resolve()
METADATA_CSV = Path(os.environ.get("KUIPER_METADATA_CSV", DATA_ROOT / "metadata.csv")).resolve()


def fix_padding(x) -> str:
    """Fix padding in audio filenames (e.g. xyz_1.wav -> 0001.wav)."""
    import re

    match = re.search(r"\d+", str(x))
    return f"{int(match.group()):04d}.wav" if match else str(x)


def get_audio_dir(data_root: Path) -> Path:
    """Get audio directory path under a given root."""
    return Path(data_root) / "wavs"


# -----------------------------------------------------------------------------
# Environment validation
# -----------------------------------------------------------------------------

class EnvironmentError(Exception):
    """Raised when the training environment is invalid."""


def validate_training_environment(
    data_root: Optional[Path] = None,
    audio_dir: Optional[Path] = None,
    metadata_csv: Optional[Path] = None,
    config_path: Optional[Path] = None,
    cleaned_ckpt: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    log_dir: Optional[Path] = None,
) -> None:
    """Validate presence and writability of key paths for training."""
    logger = get_logger(__name__)

    data_root = data_root or DATA_ROOT
    audio_dir = audio_dir or AUDIO_DIR
    metadata_csv = metadata_csv or METADATA_CSV
    config_path = config_path or CONFIG_PATH
    cleaned_ckpt = cleaned_ckpt or CLEANED_CKPT
    cache_dir = cache_dir or CACHE_DIR
    log_dir = log_dir or DRIVE_LOG_DIR

    problems = []

    if not data_root.exists():
        problems.append(f"DATA_ROOT does not exist: {data_root}")

    if not audio_dir.exists():
        problems.append(f"Audio directory does not exist: {audio_dir}")

    if not metadata_csv.exists():
        problems.append(f"metadata.csv does not exist: {metadata_csv}")

    if not config_path.exists():
        problems.append(f"Config JSON not found: {config_path}")

    if not cleaned_ckpt.exists():
        problems.append(f"Checkpoint not found: {cleaned_ckpt}")

    for d, label in [(cache_dir, "cache_dir"), (log_dir, "log_dir")]:
        try:
            d.mkdir(parents=True, exist_ok=True)
            test_file = d / ".kuiper_write_test"
            test_file.write_text("ok")
            test_file.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            problems.append(f"Cannot write to {label}={d}: {e!r}")

    if problems:
        msg = "Invalid training environment:\n  - " + "\n  - ".join(problems)
        logger.error(msg)
        raise EnvironmentError(msg)

    logger.info(
        "Training environment validated: data_root=%s audio_dir=%s metadata_csv=%s",
        data_root,
        audio_dir,
        metadata_csv,
    )


# -----------------------------------------------------------------------------
# GPU utilities & batch size selection
# -----------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = int(os.environ.get("KUIPER_DEFAULT_BATCH_SIZE", "64"))


def get_gpu_memory() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Get total, free, and allocated GPU memory in GB using torch."""
    if not torch.cuda.is_available():
        return None, None, None

    try:
        device = torch.cuda.current_device()
        props = torch.cuda.get_device_properties(device)
        total_memory = props.total_memory / (1024**3)
        allocated = torch.cuda.memory_allocated(device) / (1024**3)
        reserved = torch.cuda.memory_reserved(device) / (1024**3)
        free_memory = total_memory - reserved
        return total_memory, free_memory, allocated
    except Exception:  # noqa: BLE001
        return None, None, None


def get_gpu_memory_nvidia_smi() -> Tuple[Optional[float], Optional[float]]:
    """Fallback: Get GPU memory using nvidia-smi (MB -> GB)."""
    import subprocess

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.free", "--format=csv,nounits,noheader"],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().split("\n")
        if lines:
            total, free = map(int, lines[0].split(","))
            return total / 1024, free / 1024
    except Exception:  # noqa: BLE001
        return None, None
    return None, None


def calculate_optimal_batch_size(total_gpu_memory_gb: float, memory_per_batch_gb: float, safety_margin: float = 0.1) -> int:
    """Calculate optimal batch size based on GPU memory."""
    if memory_per_batch_gb <= 0 or total_gpu_memory_gb <= 0:
        return DEFAULT_BATCH_SIZE

    available_memory = total_gpu_memory_gb * (1 - safety_margin)
    optimal_batch = int(available_memory / memory_per_batch_gb)

    import math

    if optimal_batch > 0:
        optimal_batch = 2 ** int(math.log2(optimal_batch))

    return max(1, optimal_batch)


def auto_detect_batch_size(estimated_mem_per_batch_gb: float = 0.8) -> int:
    """Auto-detect optimal batch size based on available GPU, else default."""
    total_mem, free_mem, _ = get_gpu_memory()

    if total_mem is None:
        total_mem, free_mem = get_gpu_memory_nvidia_smi()

    if total_mem is None or free_mem is None:
        return DEFAULT_BATCH_SIZE

    return calculate_optimal_batch_size(total_gpu_memory_gb=total_mem, memory_per_batch_gb=estimated_mem_per_batch_gb)


def log_and_auto_detect_batch_size(logger: Optional[logging.Logger] = None, estimated_mem_per_batch_gb: float = 0.8) -> int:
    """Wrapper around auto_detect_batch_size with logging."""
    logger = logger or get_logger(__name__)

    total_mem, free_mem, _ = get_gpu_memory()
    source = "torch"

    if total_mem is None or free_mem is None:
        total_mem, free_mem = get_gpu_memory_nvidia_smi()
        source = "nvidia-smi"

    if total_mem is None or free_mem is None:
        logger.warning("No GPU detected or unable to query GPU memory; using default batch size=%d", DEFAULT_BATCH_SIZE)
        return DEFAULT_BATCH_SIZE

    logger.info("GPU memory (%s): total=%.2f GB, free=%.2f GB", source, total_mem, free_mem)
    batch_size = calculate_optimal_batch_size(total_gpu_memory_gb=total_mem, memory_per_batch_gb=estimated_mem_per_batch_gb)
    logger.info("Chosen batch size=%d (estimated_mem_per_batch=%.2f GB)", batch_size, estimated_mem_per_batch_gb)
    return batch_size


def measure_memory_per_batch(model, sample_batch: dict, device: Optional[torch.device] = None) -> Optional[float]:
    """Measure peak GPU memory usage for a given batch on a device.

    This is an optional tool for manual tuning; it should NOT be run at import time.
    """
    if not torch.cuda.is_available():
        return None

    device = device or torch.device("cuda")

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(device)

    model = model.to(device)
    sample_batch = {k: (v.to(device) if isinstance(v, torch.Tensor) else v) for k, v in sample_batch.items()}

    with torch.no_grad():
        _ = model(sample_batch)

    peak_memory = torch.cuda.max_memory_allocated(device) / (1024**3)
    torch.cuda.empty_cache()
    return peak_memory
