# Audio Processor Module
# Handles audio operations for recording and processing

import wave
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import math


@dataclass
class AudioDeviceInfo:
    """Information about an audio input device."""
    
    device_id: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


@dataclass
class AudioInfo:
    """Information about an audio file."""
    
    path: Path
    sample_rate: int
    channels: int
    duration_seconds: float
    samples: int
    bit_depth: int
    peak_amplitude: float
    rms_level: float
    is_valid: bool
    error: Optional[str] = None


@dataclass
class AudioLevels:
    """Real-time audio levels."""
    
    peak: float  # 0.0 to 1.0
    rms: float   # 0.0 to 1.0
    db: float    # Decibels (negative)
    is_clipping: bool


@dataclass
class MicrophoneConfig:
    """Microphone configuration settings."""
    
    device_id: Optional[int]
    sample_rate: int
    gain: float
    normalize: bool
    silence_threshold: float
    noise_reduction: bool


class AudioProcessor:
    """Process audio files and handle microphone operations."""
    
    DEFAULT_SAMPLE_RATE = 22050
    DEFAULT_CHANNELS = 1
    DEFAULT_BIT_DEPTH = 16
    
    # Quality thresholds
    MIN_DURATION_SECONDS = 0.5
    MAX_DURATION_SECONDS = 30.0
    MIN_RMS_LEVEL = 0.01
    MAX_RMS_LEVEL = 0.9
    CLIPPING_THRESHOLD = 0.99
    
    def __init__(self, sample_rate: int = DEFAULT_SAMPLE_RATE):
        """
        Initialize the audio processor.
        
        Args:
            sample_rate: Target sample rate for audio processing
        """
        self.sample_rate = sample_rate
        self._sounddevice = None
        self._numpy = None
    
    def _ensure_dependencies(self):
        """Lazily import optional dependencies."""
        if self._numpy is None:
            try:
                import numpy as np
                self._numpy = np
            except ImportError:
                raise ImportError(
                    "numpy is required for audio processing. "
                    "Install with: pip install numpy"
                )
        
        if self._sounddevice is None:
            try:
                import sounddevice as sd
                self._sounddevice = sd
            except ImportError:
                raise ImportError(
                    "sounddevice is required for microphone access. "
                    "Install with: pip install sounddevice"
                )
    
    def list_devices(self) -> List[AudioDeviceInfo]:
        """
        List all available audio input devices.
        
        Returns:
            List of AudioDeviceInfo for each input device
        """
        try:
            self._ensure_dependencies()
        except ImportError as e:
            # Return empty list if dependencies aren't installed
            return []
        
        try:
            sd = self._sounddevice
            
            devices = []
            all_devices = sd.query_devices()
            default_input = sd.default.device[0] if sd.default.device[0] is not None else -1
            
            for i, device in enumerate(all_devices):
                if device.get("max_input_channels", 0) > 0:
                    devices.append(AudioDeviceInfo(
                        device_id=i,
                        name=device.get("name", f"Device {i}"),
                        channels=device.get("max_input_channels", 1),
                        sample_rate=device.get("default_samplerate", self.sample_rate),
                        is_default=(i == default_input)
                    ))
            
            return devices
        except Exception as e:
            # Log error but return empty list instead of crashing
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to list audio devices: {e}")
            return []
    
    def get_default_device(self) -> Optional[AudioDeviceInfo]:
        """
        Get the default audio input device.
        
        Returns:
            AudioDeviceInfo for the default device, or None if no devices
        """
        devices = self.list_devices()
        for device in devices:
            if device.is_default:
                return device
        return devices[0] if devices else None
    
    def test_device(
        self,
        device_id: Optional[int] = None,
        duration_seconds: float = 1.0
    ) -> Tuple[bool, AudioLevels, Optional[str]]:
        """
        Test an audio device by recording briefly.
        
        Args:
            device_id: Device ID to test (None for default)
            duration_seconds: How long to record for testing
        
        Returns:
            Tuple of (success, audio_levels, error_message)
        """
        self._ensure_dependencies()
        sd = self._sounddevice
        np = self._numpy
        
        try:
            # Record audio
            samples = int(duration_seconds * self.sample_rate)
            recording = sd.rec(
                samples,
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=device_id
            )
            sd.wait()
            
            # Analyze levels
            audio = recording.flatten()
            peak = float(np.max(np.abs(audio)))
            rms = float(np.sqrt(np.mean(audio ** 2)))
            
            # Calculate dB (avoid log of 0)
            if rms > 0:
                db = 20 * math.log10(rms)
            else:
                db = -100
            
            levels = AudioLevels(
                peak=peak,
                rms=rms,
                db=db,
                is_clipping=(peak >= self.CLIPPING_THRESHOLD)
            )
            
            return True, levels, None
            
        except Exception as e:
            return False, AudioLevels(0, 0, -100, False), str(e)
    
    def analyze_file(self, path: Path) -> AudioInfo:
        """
        Analyze an audio file and return its properties.
        
        Args:
            path: Path to the audio file
        
        Returns:
            AudioInfo with file properties and quality metrics
        """
        path = Path(path)
        
        if not path.exists():
            return AudioInfo(
                path=path,
                sample_rate=0,
                channels=0,
                duration_seconds=0,
                samples=0,
                bit_depth=0,
                peak_amplitude=0,
                rms_level=0,
                is_valid=False,
                error=f"File not found: {path}"
            )
        
        try:
            # Try with librosa first (better format support)
            return self._analyze_with_librosa(path)
        except ImportError:
            pass
        
        try:
            # Fall back to wave module for WAV files
            return self._analyze_with_wave(path)
        except Exception as e:
            return AudioInfo(
                path=path,
                sample_rate=0,
                channels=0,
                duration_seconds=0,
                samples=0,
                bit_depth=0,
                peak_amplitude=0,
                rms_level=0,
                is_valid=False,
                error=str(e)
            )
    
    def _analyze_with_librosa(self, path: Path) -> AudioInfo:
        """Analyze audio using librosa."""
        import librosa
        import numpy as np
        
        # Load audio
        y, sr = librosa.load(path, sr=None, mono=True)
        
        # Calculate metrics
        duration = len(y) / sr
        peak = float(np.max(np.abs(y)))
        rms = float(np.sqrt(np.mean(y ** 2)))
        
        # Validate
        is_valid = True
        error = None
        
        if duration < self.MIN_DURATION_SECONDS:
            is_valid = False
            error = f"Audio too short ({duration:.2f}s < {self.MIN_DURATION_SECONDS}s)"
        elif duration > self.MAX_DURATION_SECONDS:
            is_valid = False
            error = f"Audio too long ({duration:.2f}s > {self.MAX_DURATION_SECONDS}s)"
        elif rms < self.MIN_RMS_LEVEL:
            is_valid = False
            error = f"Audio too quiet (RMS {rms:.3f} < {self.MIN_RMS_LEVEL})"
        elif peak >= self.CLIPPING_THRESHOLD:
            is_valid = False
            error = "Audio is clipping (peak amplitude too high)"
        
        return AudioInfo(
            path=path,
            sample_rate=sr,
            channels=1,
            duration_seconds=duration,
            samples=len(y),
            bit_depth=16,  # librosa converts to float, assume 16-bit source
            peak_amplitude=peak,
            rms_level=rms,
            is_valid=is_valid,
            error=error
        )
    
    def _analyze_with_wave(self, path: Path) -> AudioInfo:
        """Analyze audio using wave module (WAV files only)."""
        with wave.open(str(path), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            samples = wf.getnframes()
            bit_depth = wf.getsampwidth() * 8
            duration = samples / sample_rate
            
            # Read all frames
            frames = wf.readframes(samples)
        
        # Convert to normalized float values
        if bit_depth == 16:
            format_str = f"<{samples * channels}h"
            max_val = 32768.0
        elif bit_depth == 8:
            format_str = f"<{samples * channels}B"
            max_val = 128.0
        else:
            # Unsupported bit depth
            return AudioInfo(
                path=path,
                sample_rate=sample_rate,
                channels=channels,
                duration_seconds=duration,
                samples=samples,
                bit_depth=bit_depth,
                peak_amplitude=0,
                rms_level=0,
                is_valid=False,
                error=f"Unsupported bit depth: {bit_depth}"
            )
        
        try:
            values = struct.unpack(format_str, frames)
            normalized = [v / max_val for v in values]
            
            # Calculate metrics
            peak = max(abs(v) for v in normalized)
            rms = math.sqrt(sum(v ** 2 for v in normalized) / len(normalized))
        except Exception:
            peak = 0
            rms = 0
        
        # Validate
        is_valid = True
        error = None
        
        if duration < self.MIN_DURATION_SECONDS:
            is_valid = False
            error = f"Audio too short ({duration:.2f}s)"
        elif duration > self.MAX_DURATION_SECONDS:
            is_valid = False
            error = f"Audio too long ({duration:.2f}s)"
        elif rms < self.MIN_RMS_LEVEL:
            is_valid = False
            error = f"Audio too quiet (RMS {rms:.3f})"
        elif peak >= self.CLIPPING_THRESHOLD:
            is_valid = False
            error = "Audio is clipping"
        
        return AudioInfo(
            path=path,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration,
            samples=samples,
            bit_depth=bit_depth,
            peak_amplitude=peak,
            rms_level=rms,
            is_valid=is_valid,
            error=error
        )
    
    def normalize_audio(
        self,
        input_path: Path,
        output_path: Path,
        target_rms: float = 0.1,
        target_sample_rate: Optional[int] = None
    ) -> AudioInfo:
        """
        Normalize audio file to target RMS level and sample rate.
        
        Args:
            input_path: Path to input audio file
            output_path: Path to write normalized audio
            target_rms: Target RMS level (0.0 to 1.0)
            target_sample_rate: Target sample rate (None to keep original)
        
        Returns:
            AudioInfo for the normalized file
        """
        try:
            import librosa
            import numpy as np
            import soundfile as sf
        except ImportError:
            raise ImportError(
                "librosa and soundfile are required for audio normalization. "
                "Install with: pip install librosa soundfile"
            )
        
        target_sr = target_sample_rate or self.sample_rate
        
        # Load audio
        y, sr = librosa.load(input_path, sr=target_sr, mono=True)
        
        # Calculate current RMS
        current_rms = np.sqrt(np.mean(y ** 2))
        
        # Normalize
        if current_rms > 0:
            gain = target_rms / current_rms
            y = y * gain
            
            # Prevent clipping
            max_val = np.max(np.abs(y))
            if max_val > 0.99:
                y = y * (0.99 / max_val)
        
        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(output_path), y, target_sr)
        
        return self.analyze_file(output_path)
    
    def save_recording(
        self,
        audio_data: bytes,
        output_path: Path,
        sample_rate: Optional[int] = None,
        channels: int = 1,
        bit_depth: int = 16,
        gain: float = 1.0,
        normalize: bool = False
    ) -> AudioInfo:
        """
        Save raw audio data to a WAV file.
        
        Args:
            audio_data: Raw audio bytes (int16 format)
            output_path: Path to save the file
            sample_rate: Sample rate (defaults to processor's rate)
            channels: Number of channels
            bit_depth: Bits per sample
            gain: Gain multiplier to apply
            normalize: Whether to normalize the audio
        
        Returns:
            AudioInfo for the saved file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        sr = sample_rate or self.sample_rate
        
        # Apply gain if specified
        if gain != 1.0 and bit_depth == 16:
            try:
                import numpy as np
                samples = np.frombuffer(audio_data, dtype=np.int16)
                samples = (samples.astype(np.float32) * gain).clip(-32768, 32767)
                audio_data = samples.astype(np.int16).tobytes()
            except ImportError:
                pass  # Skip gain if numpy not available
        
        # Write WAV file
        with wave.open(str(output_path), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(bit_depth // 8)
            wf.setframerate(sr)
            wf.writeframes(audio_data)
        
        # Normalize if requested
        if normalize:
            try:
                return self.normalize_audio(output_path, output_path)
            except ImportError:
                pass  # Skip normalization if libraries not available
        
        return self.analyze_file(output_path)
    
    def get_recommended_gain(
        self,
        device_id: Optional[int] = None,
        test_duration: float = 3.0
    ) -> Tuple[float, AudioLevels]:
        """
        Test microphone and recommend gain setting.
        
        Args:
            device_id: Device to test (None for default)
            test_duration: How long to record for testing
        
        Returns:
            Tuple of (recommended_gain, audio_levels)
        """
        success, levels, error = self.test_device(device_id, test_duration)
        
        if not success:
            return 1.0, levels
        
        # Target RMS of 0.1 (good level for TTS training)
        target_rms = 0.1
        
        if levels.rms > 0:
            recommended_gain = target_rms / levels.rms
            # Clamp to reasonable range
            recommended_gain = max(0.5, min(5.0, recommended_gain))
        else:
            recommended_gain = 1.0
        
        return recommended_gain, levels


def list_audio_devices() -> List[Dict[str, Any]]:
    """
    Convenience function to list audio devices.
    
    Returns:
        List of device dictionaries
    """
    processor = AudioProcessor()
    devices = processor.list_devices()
    return [
        {
            "device_id": d.device_id,
            "name": d.name,
            "channels": d.channels,
            "sample_rate": d.sample_rate,
            "is_default": d.is_default
        }
        for d in devices
    ]

