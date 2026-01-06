# System Analyzer Module
# Detects hardware capabilities for TTS training

import os
import platform
import subprocess
import shutil
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Tuple
from pathlib import Path


@dataclass
class GPUInfo:
    """Information about a detected GPU."""
    
    name: str
    vendor: str  # "nvidia", "amd", "apple", "none"
    vram_total_gb: float
    vram_free_gb: float
    cuda_version: Optional[str] = None
    compute_capability: Optional[str] = None
    driver_version: Optional[str] = None
    is_available: bool = True


@dataclass
class CPUInfo:
    """Information about the CPU."""
    
    name: str
    cores_physical: int
    cores_logical: int
    frequency_mhz: float
    architecture: str


@dataclass
class MemoryInfo:
    """Information about system memory."""
    
    total_gb: float
    available_gb: float
    used_gb: float
    percent_used: float


@dataclass
class StorageInfo:
    """Information about storage."""
    
    path: str
    total_gb: float
    free_gb: float
    percent_used: float


@dataclass
class TrainingEstimate:
    """Estimated training times for different sample counts."""
    
    samples_100: str
    samples_500: str
    samples_1000: str
    recommended_batch_size: int
    recommended_epochs: int
    memory_per_batch_mb: float


@dataclass
class SystemReport:
    """Complete system analysis report."""
    
    # Hardware info
    gpu: Optional[GPUInfo]
    cpu: CPUInfo
    memory: MemoryInfo
    storage: StorageInfo
    
    # Software info
    python_version: str
    cuda_available: bool
    mps_available: bool  # Apple Metal
    rocm_available: bool  # AMD
    
    # Compatibility
    can_train: bool
    training_backend: str  # "cuda", "mps", "cpu"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Estimates
    estimates: Optional[TrainingEstimate] = None


class SystemAnalyzer:
    """Analyze system capabilities for TTS training."""
    
    # Memory requirements per sample (approximate, in MB)
    MEMORY_PER_SAMPLE_MB = 0.8
    
    # Minimum requirements
    MIN_VRAM_GB = 4.0
    MIN_RAM_GB = 8.0
    MIN_STORAGE_GB = 10.0
    
    # GPU speed factors (relative to RTX 3090)
    GPU_SPEED_FACTORS = {
        # NVIDIA
        "4090": 1.5,
        "4080": 1.3,
        "4070": 1.1,
        "3090": 1.0,
        "3080": 0.9,
        "3070": 0.75,
        "3060": 0.6,
        "2080": 0.7,
        "2070": 0.55,
        "2060": 0.45,
        "1080": 0.4,
        "1070": 0.3,
        "A6000": 1.2,
        "A5000": 1.0,
        "A4000": 0.8,
        # Apple
        "M1": 0.3,
        "M2": 0.4,
        "M3": 0.5,
        "M1 Pro": 0.4,
        "M2 Pro": 0.5,
        "M3 Pro": 0.6,
        "M1 Max": 0.5,
        "M2 Max": 0.6,
        "M3 Max": 0.7,
        "M1 Ultra": 0.7,
        "M2 Ultra": 0.8,
    }
    
    def analyze(self, data_path: Optional[Path] = None) -> SystemReport:
        """
        Perform complete system analysis.
        
        Args:
            data_path: Path to check storage for (defaults to current directory)
        
        Returns:
            SystemReport with all hardware and compatibility information
        """
        gpu = self._check_gpu()
        cpu = self._check_cpu()
        memory = self._check_memory()
        storage = self._check_storage(data_path or Path.cwd())
        
        python_version = platform.python_version()
        cuda_available = self._check_cuda()
        mps_available = self._check_mps()
        rocm_available = self._check_rocm()
        
        # Determine training backend
        if cuda_available and gpu and gpu.vendor == "nvidia":
            training_backend = "cuda"
        elif mps_available:
            training_backend = "mps"
        elif rocm_available and gpu and gpu.vendor == "amd":
            training_backend = "rocm"
        else:
            training_backend = "cpu"
        
        # Check compatibility
        can_train, warnings, errors = self._check_compatibility(
            gpu, memory, storage, training_backend
        )
        
        # Calculate estimates
        estimates = self._calculate_estimates(gpu, training_backend)
        
        return SystemReport(
            gpu=gpu,
            cpu=cpu,
            memory=memory,
            storage=storage,
            python_version=python_version,
            cuda_available=cuda_available,
            mps_available=mps_available,
            rocm_available=rocm_available,
            can_train=can_train,
            training_backend=training_backend,
            warnings=warnings,
            errors=errors,
            estimates=estimates,
        )
    
    def _check_gpu(self) -> Optional[GPUInfo]:
        """Detect GPU information."""
        # Try NVIDIA first
        nvidia_gpu = self._check_nvidia_gpu()
        if nvidia_gpu:
            return nvidia_gpu
        
        # Try Apple Silicon
        apple_gpu = self._check_apple_gpu()
        if apple_gpu:
            return apple_gpu
        
        # Try AMD
        amd_gpu = self._check_amd_gpu()
        if amd_gpu:
            return amd_gpu
        
        return None
    
    def _check_nvidia_gpu(self) -> Optional[GPUInfo]:
        """Check for NVIDIA GPU using nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.free,driver_version",
                    "--format=csv,nounits,noheader"
                ],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            
            lines = result.stdout.strip().split("\n")
            if lines and lines[0]:
                parts = [p.strip() for p in lines[0].split(",")]
                if len(parts) >= 4:
                    name = parts[0]
                    total_mb = float(parts[1])
                    free_mb = float(parts[2])
                    driver = parts[3]
                    
                    # Get CUDA version
                    cuda_version = self._get_cuda_version()
                    
                    return GPUInfo(
                        name=name,
                        vendor="nvidia",
                        vram_total_gb=total_mb / 1024,
                        vram_free_gb=free_mb / 1024,
                        cuda_version=cuda_version,
                        driver_version=driver,
                        is_available=True
                    )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return None
    
    def _check_apple_gpu(self) -> Optional[GPUInfo]:
        """Check for Apple Silicon GPU."""
        if platform.system() != "Darwin":
            return None
        
        try:
            # Check if running on Apple Silicon
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            cpu_name = result.stdout.strip()
            
            if "Apple" in cpu_name:
                # Get memory info (unified memory on Apple Silicon)
                mem_result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=5
                )
                total_bytes = int(mem_result.stdout.strip())
                total_gb = total_bytes / (1024 ** 3)
                
                # Estimate GPU memory as portion of unified memory
                # Apple Silicon typically allocates up to 75% for GPU
                gpu_mem_gb = total_gb * 0.75
                
                # Determine chip type
                chip_name = "Apple Silicon"
                for chip in ["M3 Ultra", "M2 Ultra", "M1 Ultra", 
                            "M3 Max", "M2 Max", "M1 Max",
                            "M3 Pro", "M2 Pro", "M1 Pro",
                            "M3", "M2", "M1"]:
                    if chip in cpu_name:
                        chip_name = chip
                        break
                
                return GPUInfo(
                    name=f"{chip_name} GPU",
                    vendor="apple",
                    vram_total_gb=gpu_mem_gb,
                    vram_free_gb=gpu_mem_gb * 0.8,  # Estimate
                    is_available=True
                )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return None
    
    def _check_amd_gpu(self) -> Optional[GPUInfo]:
        """Check for AMD GPU."""
        # Try rocm-smi for AMD GPUs
        try:
            result = subprocess.run(
                ["rocm-smi", "--showmeminfo", "vram"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10
            )
            # Parse output (format varies)
            # This is a simplified check
            if result.returncode == 0:
                return GPUInfo(
                    name="AMD GPU",
                    vendor="amd",
                    vram_total_gb=8.0,  # Default estimate
                    vram_free_gb=6.0,
                    is_available=True
                )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        return None
    
    def _get_cuda_version(self) -> Optional[str]:
        """Get CUDA version."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                check=True,
                timeout=5
            )
            # Try to get CUDA version from nvcc
            nvcc_result = subprocess.run(
                ["nvcc", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if nvcc_result.returncode == 0:
                for line in nvcc_result.stdout.split("\n"):
                    if "release" in line.lower():
                        # Extract version like "12.1"
                        import re
                        match = re.search(r"release (\d+\.\d+)", line)
                        if match:
                            return match.group(1)
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            pass
        
        # Try PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                return torch.version.cuda
        except ImportError:
            pass
        
        return None
    
    def _check_cpu(self) -> CPUInfo:
        """Get CPU information."""
        try:
            import multiprocessing
            cores_logical = multiprocessing.cpu_count()
        except Exception:
            cores_logical = os.cpu_count() or 1
        
        # Physical cores (estimate as half of logical on hyperthreaded systems)
        cores_physical = max(1, cores_logical // 2)
        
        # Get CPU name
        cpu_name = platform.processor() or "Unknown"
        if platform.system() == "Darwin":
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    cpu_name = result.stdout.strip()
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if "model name" in line:
                            cpu_name = line.split(":")[1].strip()
                            break
            except Exception:
                pass
        
        # Get frequency
        freq_mhz = 0.0
        try:
            import psutil
            freq = psutil.cpu_freq()
            if freq:
                freq_mhz = freq.current
        except ImportError:
            pass
        
        return CPUInfo(
            name=cpu_name,
            cores_physical=cores_physical,
            cores_logical=cores_logical,
            frequency_mhz=freq_mhz,
            architecture=platform.machine()
        )
    
    def _check_memory(self) -> MemoryInfo:
        """Get system memory information."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return MemoryInfo(
                total_gb=mem.total / (1024 ** 3),
                available_gb=mem.available / (1024 ** 3),
                used_gb=mem.used / (1024 ** 3),
                percent_used=mem.percent
            )
        except ImportError:
            # Fallback for systems without psutil
            if platform.system() == "Darwin":
                try:
                    result = subprocess.run(
                        ["sysctl", "-n", "hw.memsize"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    total_bytes = int(result.stdout.strip())
                    total_gb = total_bytes / (1024 ** 3)
                    return MemoryInfo(
                        total_gb=total_gb,
                        available_gb=total_gb * 0.5,  # Estimate
                        used_gb=total_gb * 0.5,
                        percent_used=50.0
                    )
                except Exception:
                    pass
            
            return MemoryInfo(
                total_gb=8.0,
                available_gb=4.0,
                used_gb=4.0,
                percent_used=50.0
            )
    
    def _check_storage(self, path: Path) -> StorageInfo:
        """Get storage information for a path."""
        try:
            import shutil
            usage = shutil.disk_usage(path)
            return StorageInfo(
                path=str(path),
                total_gb=usage.total / (1024 ** 3),
                free_gb=usage.free / (1024 ** 3),
                percent_used=(usage.used / usage.total) * 100
            )
        except Exception:
            return StorageInfo(
                path=str(path),
                total_gb=100.0,
                free_gb=50.0,
                percent_used=50.0
            )
    
    def _check_cuda(self) -> bool:
        """Check if CUDA is available."""
        try:
            import torch
            return torch.cuda.is_available()
        except (ImportError, Exception):
            # Check for nvidia-smi as fallback
            return shutil.which("nvidia-smi") is not None
    
    def _check_mps(self) -> bool:
        """Check if Apple Metal (MPS) is available."""
        if platform.system() != "Darwin":
            return False
        
        try:
            import torch
            return torch.backends.mps.is_available()
        except (ImportError, AttributeError, Exception):
            # Check if running on Apple Silicon
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return "Apple" in result.stdout
            except Exception:
                return False
    
    def _check_rocm(self) -> bool:
        """Check if AMD ROCm is available."""
        try:
            import torch
            return torch.cuda.is_available() and "rocm" in torch.__version__.lower()
        except ImportError:
            return shutil.which("rocm-smi") is not None
    
    def _check_compatibility(
        self,
        gpu: Optional[GPUInfo],
        memory: MemoryInfo,
        storage: StorageInfo,
        backend: str
    ) -> Tuple[bool, List[str], List[str]]:
        """Check if system meets minimum requirements."""
        warnings = []
        errors = []
        can_train = True
        
        # Check GPU/backend
        if backend == "cpu":
            warnings.append(
                "No GPU detected. Training on CPU will be very slow (10-50x slower)."
            )
        elif gpu:
            if gpu.vram_total_gb < self.MIN_VRAM_GB:
                errors.append(
                    f"GPU VRAM ({gpu.vram_total_gb:.1f} GB) below minimum "
                    f"requirement ({self.MIN_VRAM_GB} GB)."
                )
                can_train = False
            elif gpu.vram_total_gb < 8:
                warnings.append(
                    f"GPU VRAM ({gpu.vram_total_gb:.1f} GB) is limited. "
                    "You may need to use smaller batch sizes."
                )
        
        # Check RAM
        if memory.total_gb < self.MIN_RAM_GB:
            errors.append(
                f"System RAM ({memory.total_gb:.1f} GB) below minimum "
                f"requirement ({self.MIN_RAM_GB} GB)."
            )
            can_train = False
        elif memory.available_gb < 4:
            warnings.append(
                f"Available RAM ({memory.available_gb:.1f} GB) is low. "
                "Close other applications before training."
            )
        
        # Check storage
        if storage.free_gb < self.MIN_STORAGE_GB:
            errors.append(
                f"Free storage ({storage.free_gb:.1f} GB) below minimum "
                f"requirement ({self.MIN_STORAGE_GB} GB)."
            )
            can_train = False
        elif storage.free_gb < 20:
            warnings.append(
                f"Free storage ({storage.free_gb:.1f} GB) is limited. "
                "Consider freeing up space for cache files."
            )
        
        return can_train, warnings, errors
    
    def _calculate_estimates(
        self,
        gpu: Optional[GPUInfo],
        backend: str
    ) -> TrainingEstimate:
        """Calculate training time estimates based on hardware."""
        # Get GPU speed factor
        speed_factor = 0.1  # CPU baseline
        
        if gpu:
            for gpu_model, factor in self.GPU_SPEED_FACTORS.items():
                if gpu_model.lower() in gpu.name.lower():
                    speed_factor = factor
                    break
            else:
                # Default factors by vendor
                if gpu.vendor == "nvidia":
                    speed_factor = 0.5  # Unknown NVIDIA
                elif gpu.vendor == "apple":
                    speed_factor = 0.4  # Unknown Apple
                elif gpu.vendor == "amd":
                    speed_factor = 0.4  # Unknown AMD
        
        # Base times (seconds) for RTX 3090 reference
        base_time_100 = 30 * 60    # 30 minutes
        base_time_500 = 150 * 60   # 2.5 hours
        base_time_1000 = 300 * 60  # 5 hours
        
        # Adjust by speed factor
        from . import format_duration
        
        time_100 = format_duration(base_time_100 / speed_factor)
        time_500 = format_duration(base_time_500 / speed_factor)
        time_1000 = format_duration(base_time_1000 / speed_factor)
        
        # Calculate recommended batch size based on VRAM
        if gpu:
            vram_gb = gpu.vram_free_gb
            # Rough estimate: each batch sample needs ~0.5 GB
            max_batch = int(vram_gb / 0.5)
            # Round to power of 2
            from . import round_to_power_of_2
            recommended_batch = min(64, max(4, round_to_power_of_2(max_batch)))
        else:
            recommended_batch = 8  # CPU default
        
        return TrainingEstimate(
            samples_100=time_100,
            samples_500=time_500,
            samples_1000=time_1000,
            recommended_batch_size=recommended_batch,
            recommended_epochs=2000,
            memory_per_batch_mb=self.MEMORY_PER_SAMPLE_MB * recommended_batch * 1024
        )


def get_system_report(data_path: Optional[Path] = None) -> SystemReport:
    """
    Convenience function to get a system report.
    
    Args:
        data_path: Optional path to check storage for
    
    Returns:
        SystemReport with all system information
    """
    analyzer = SystemAnalyzer()
    return analyzer.analyze(data_path)

