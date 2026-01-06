# Data Preparer Module
# Bridges recordings to training data format

import csv
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Tuple


@dataclass
class RecordingInfo:
    """Information about a single recording."""
    
    wav_path: Path
    text: str
    index: int
    source_file: str  # Original text file name
    is_valid: bool = True
    duration_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class TextScript:
    """A text script file with lines to record."""
    
    path: Path
    name: str  # Stem of the file
    lines: List[str] = field(default_factory=list)
    
    @classmethod
    def from_file(cls, path: Path) -> "TextScript":
        """Load a text script from a file."""
        path = Path(path)
        lines = []
        
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
        
        return cls(path=path, name=path.stem, lines=lines)


@dataclass
class DatasetInfo:
    """Information about a prepared dataset."""
    
    name: str
    total_recordings: int
    valid_recordings: int
    invalid_recordings: int
    total_duration_seconds: float
    metadata_path: Path
    audio_dir: Path
    recordings: List[RecordingInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DataPreparer:
    """
    Prepare recording data for TTS training.
    
    This class handles:
    - Scanning recordings directory for WAV files
    - Matching recordings to original text files
    - Generating metadata.csv in piper format
    - Validating audio files
    - Organizing files for training
    """
    
    # Expected naming pattern: {script_name}_{index:04d}.wav
    RECORDING_PATTERN = re.compile(r"^(.+?)_(\d+)\.wav$", re.IGNORECASE)
    
    def __init__(
        self,
        recordings_dir: Path,
        output_dir: Path,
        sample_rate: int = 22050
    ):
        """
        Initialize the data preparer.
        
        Args:
            recordings_dir: Directory containing recorded WAV files
            output_dir: Output directory for training data
            sample_rate: Expected sample rate for audio files
        """
        self.recordings_dir = Path(recordings_dir)
        self.output_dir = Path(output_dir)
        self.sample_rate = sample_rate
        self._audio_processor = None
    
    def _get_audio_processor(self):
        """Lazily import audio processor."""
        if self._audio_processor is None:
            from .audio_processor import AudioProcessor
            self._audio_processor = AudioProcessor(self.sample_rate)
        return self._audio_processor
    
    def scan_recordings(self) -> Dict[str, List[Tuple[int, Path]]]:
        """
        Scan recordings directory and group by source script.
        
        Returns:
            Dictionary mapping script names to list of (index, path) tuples
        """
        recordings: Dict[str, List[Tuple[int, Path]]] = {}
        
        if not self.recordings_dir.exists():
            return recordings
        
        for wav_file in self.recordings_dir.glob("*.wav"):
            match = self.RECORDING_PATTERN.match(wav_file.name)
            if match:
                script_name = match.group(1)
                index = int(match.group(2))
                
                if script_name not in recordings:
                    recordings[script_name] = []
                
                recordings[script_name].append((index, wav_file))
        
        # Sort each group by index
        for script_name in recordings:
            recordings[script_name].sort(key=lambda x: x[0])
        
        return recordings
    
    def find_script_file(
        self,
        script_name: str,
        search_dirs: Optional[List[Path]] = None
    ) -> Optional[Path]:
        """
        Find the text script file for a given script name.
        
        Args:
            script_name: Name of the script (without extension)
            search_dirs: Directories to search in
        
        Returns:
            Path to the script file, or None if not found
        """
        if search_dirs is None:
            # Default search locations
            search_dirs = [
                self.recordings_dir.parent,  # Same level as recordings
                self.recordings_dir,          # Inside recordings
                Path.cwd(),                   # Current directory
            ]
        
        for search_dir in search_dirs:
            for ext in [".txt", ".text", ""]:
                script_path = search_dir / f"{script_name}{ext}"
                if script_path.exists():
                    return script_path
        
        return None
    
    def match_recordings_to_text(
        self,
        script: TextScript,
        recordings: List[Tuple[int, Path]]
    ) -> List[RecordingInfo]:
        """
        Match recordings to their corresponding text lines.
        
        Args:
            script: The text script
            recordings: List of (index, path) tuples for recordings
        
        Returns:
            List of RecordingInfo with matched text
        """
        processor = self._get_audio_processor()
        results = []
        
        for index, wav_path in recordings:
            # Text indices are 1-based in filenames
            text_index = index - 1
            
            if text_index < 0 or text_index >= len(script.lines):
                results.append(RecordingInfo(
                    wav_path=wav_path,
                    text="",
                    index=index,
                    source_file=script.name,
                    is_valid=False,
                    error=f"No matching text for index {index}"
                ))
                continue
            
            text = script.lines[text_index]
            
            # Analyze audio file
            audio_info = processor.analyze_file(wav_path)
            
            results.append(RecordingInfo(
                wav_path=wav_path,
                text=text,
                index=index,
                source_file=script.name,
                is_valid=audio_info.is_valid,
                duration_seconds=audio_info.duration_seconds,
                error=audio_info.error
            ))
        
        return results
    
    def prepare_dataset(
        self,
        script_files: Optional[List[Path]] = None,
        voice_name: str = "kuiper",
        copy_files: bool = True,
        validate_audio: bool = True
    ) -> DatasetInfo:
        """
        Prepare a complete dataset for training.
        
        Args:
            script_files: List of text script files (auto-detect if None)
            voice_name: Name for the voice
            copy_files: Whether to copy files to output directory
            validate_audio: Whether to validate audio files
        
        Returns:
            DatasetInfo with preparation results
        """
        errors = []
        warnings = []
        all_recordings: List[RecordingInfo] = []
        
        # Scan recordings
        recording_groups = self.scan_recordings()
        
        if not recording_groups:
            errors.append(f"No recordings found in {self.recordings_dir}")
            return DatasetInfo(
                name=voice_name,
                total_recordings=0,
                valid_recordings=0,
                invalid_recordings=0,
                total_duration_seconds=0,
                metadata_path=self.output_dir / "metadata.csv",
                audio_dir=self.output_dir / "wavs",
                errors=errors
            )
        
        # Process each recording group
        for script_name, recordings in recording_groups.items():
            # Find the corresponding script file
            script_path = self.find_script_file(script_name)
            
            if script_path is None:
                if script_files:
                    # Try provided script files
                    for sf in script_files:
                        if sf.stem == script_name:
                            script_path = sf
                            break
            
            if script_path is None:
                warnings.append(
                    f"Could not find text file for '{script_name}'. "
                    f"Expected: {script_name}.txt"
                )
                continue
            
            script = TextScript.from_file(script_path)
            
            if not script.lines:
                warnings.append(f"Script file is empty: {script_path}")
                continue
            
            # Match recordings to text
            matched = self.match_recordings_to_text(script, recordings)
            all_recordings.extend(matched)
            
            # Check for missing recordings
            recorded_indices = {r.index for r in matched}
            for i in range(1, len(script.lines) + 1):
                if i not in recorded_indices:
                    warnings.append(
                        f"Missing recording for '{script_name}' line {i}: "
                        f"\"{script.lines[i-1][:50]}...\""
                    )
        
        # Create output directories
        audio_dir = self.output_dir / "wavs"
        audio_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate metadata and copy files
        metadata_path = self.output_dir / "metadata.csv"
        valid_recordings = []
        invalid_recordings = []
        
        for recording in all_recordings:
            if recording.is_valid:
                valid_recordings.append(recording)
            else:
                invalid_recordings.append(recording)
        
        # Write metadata.csv
        with open(metadata_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f, delimiter="|")
            
            for i, recording in enumerate(valid_recordings, start=1):
                # Use 4-digit padded filename
                new_filename = f"{i:04d}.wav"
                
                if copy_files:
                    dest_path = audio_dir / new_filename
                    shutil.copy2(recording.wav_path, dest_path)
                
                # Write metadata row: filename|text
                writer.writerow([new_filename, recording.text])
        
        # Calculate total duration
        total_duration = sum(r.duration_seconds for r in valid_recordings)
        
        # Log errors for invalid recordings
        for recording in invalid_recordings:
            if recording.error:
                errors.append(
                    f"Invalid recording {recording.wav_path.name}: {recording.error}"
                )
        
        return DatasetInfo(
            name=voice_name,
            total_recordings=len(all_recordings),
            valid_recordings=len(valid_recordings),
            invalid_recordings=len(invalid_recordings),
            total_duration_seconds=total_duration,
            metadata_path=metadata_path,
            audio_dir=audio_dir,
            recordings=all_recordings,
            errors=errors,
            warnings=warnings
        )
    
    def validate_dataset(self, metadata_path: Path) -> DatasetInfo:
        """
        Validate an existing dataset.
        
        Args:
            metadata_path: Path to metadata.csv file
        
        Returns:
            DatasetInfo with validation results
        """
        metadata_path = Path(metadata_path)
        audio_dir = metadata_path.parent / "wavs"
        
        errors = []
        warnings = []
        recordings = []
        
        if not metadata_path.exists():
            errors.append(f"Metadata file not found: {metadata_path}")
            return DatasetInfo(
                name="unknown",
                total_recordings=0,
                valid_recordings=0,
                invalid_recordings=0,
                total_duration_seconds=0,
                metadata_path=metadata_path,
                audio_dir=audio_dir,
                errors=errors
            )
        
        processor = self._get_audio_processor()
        
        with open(metadata_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="|")
            
            for i, row in enumerate(reader, start=1):
                if len(row) < 2:
                    errors.append(f"Invalid row {i}: expected 'filename|text'")
                    continue
                
                filename, text = row[0], row[1]
                wav_path = audio_dir / filename
                
                if not wav_path.exists():
                    recordings.append(RecordingInfo(
                        wav_path=wav_path,
                        text=text,
                        index=i,
                        source_file="metadata.csv",
                        is_valid=False,
                        error=f"File not found: {filename}"
                    ))
                    continue
                
                audio_info = processor.analyze_file(wav_path)
                
                recordings.append(RecordingInfo(
                    wav_path=wav_path,
                    text=text,
                    index=i,
                    source_file="metadata.csv",
                    is_valid=audio_info.is_valid,
                    duration_seconds=audio_info.duration_seconds,
                    error=audio_info.error
                ))
        
        valid = [r for r in recordings if r.is_valid]
        invalid = [r for r in recordings if not r.is_valid]
        
        for r in invalid:
            if r.error:
                errors.append(f"{r.wav_path.name}: {r.error}")
        
        return DatasetInfo(
            name=metadata_path.parent.name,
            total_recordings=len(recordings),
            valid_recordings=len(valid),
            invalid_recordings=len(invalid),
            total_duration_seconds=sum(r.duration_seconds for r in valid),
            metadata_path=metadata_path,
            audio_dir=audio_dir,
            recordings=recordings,
            errors=errors,
            warnings=warnings
        )
    
    def get_recording_progress(
        self,
        script_files: List[Path]
    ) -> Dict[str, Dict[str, int]]:
        """
        Get recording progress for each script.
        
        Args:
            script_files: List of text script files
        
        Returns:
            Dictionary mapping script names to progress info
        """
        recording_groups = self.scan_recordings()
        progress = {}
        
        for script_path in script_files:
            script = TextScript.from_file(script_path)
            script_name = script.name
            
            recorded = len(recording_groups.get(script_name, []))
            total = len(script.lines)
            
            progress[script_name] = {
                "recorded": recorded,
                "total": total,
                "remaining": max(0, total - recorded),
                "percent": int((recorded / total * 100) if total > 0 else 0)
            }
        
        return progress


def prepare_training_data(
    recordings_dir: Path,
    output_dir: Path,
    script_files: Optional[List[Path]] = None,
    voice_name: str = "kuiper"
) -> DatasetInfo:
    """
    Convenience function to prepare training data.
    
    Args:
        recordings_dir: Directory containing WAV recordings
        output_dir: Output directory for training data
        script_files: Optional list of text script files
        voice_name: Name for the voice
    
    Returns:
        DatasetInfo with preparation results
    """
    preparer = DataPreparer(recordings_dir, output_dir)
    return preparer.prepare_dataset(script_files, voice_name)

