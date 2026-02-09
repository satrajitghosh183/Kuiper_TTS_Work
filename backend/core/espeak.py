"""eSpeak NG integration for pronunciation generation."""
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ESpeakNG:
    """Wrapper for eSpeak NG TTS engine."""
    
    def __init__(self, voice: str = "en", speed: int = 150):
        self.voice = voice
        self.speed = speed
        self.sample_rate = 22050
    
    def generate_pronunciation(
        self,
        text: str,
        output_path: Optional[Path] = None,
        voice: Optional[str] = None
    ) -> Path:
        """Generate audio pronunciation using eSpeak NG."""
        if output_path is None:
            output_path = Path(tempfile.mktemp(suffix='.wav'))
        
        voice_arg = voice or self.voice
        
        cmd = [
            'espeak-ng',
            '-v', voice_arg,
            '-s', str(self.speed),
            '-w', str(output_path),
            text
        ]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True,
                timeout=10  # 10 second timeout
            )
            if result.returncode != 0:
                raise RuntimeError(f"eSpeak NG failed: {result.stderr}")
            
            if not output_path.exists():
                raise RuntimeError(f"eSpeak NG did not create output file: {output_path}")
            
            return output_path
        except subprocess.TimeoutExpired:
            raise RuntimeError("eSpeak NG timed out")
        except FileNotFoundError:
            raise RuntimeError("eSpeak NG not found. Please install espeak-ng.")
    
    def is_available(self) -> bool:
        """Check if eSpeak NG is installed."""
        try:
            result = subprocess.run(
                ['espeak-ng', '--version'], 
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
