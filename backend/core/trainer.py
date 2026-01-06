# Trainer Module
# Wraps Piper TTS training with progress callbacks

import json
import sys
import time
import threading
import queue
import logging
import re
import io
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List

# Configure logging
logger = logging.getLogger('kuiper.trainer')


class TrainingStatus(Enum):
    """Training status states."""
    IDLE = "idle"
    PREPARING = "preparing"
    TRAINING = "training"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TrainingProgress:
    """Current training progress."""
    
    status: TrainingStatus
    epoch: int
    total_epochs: int
    step: int
    total_steps: int
    loss: float
    val_loss: Optional[float]
    learning_rate: float
    elapsed_seconds: float
    estimated_remaining_seconds: float
    samples_per_second: float
    checkpoints_saved: int
    last_checkpoint_path: Optional[Path]
    started_at: Optional[datetime]
    message: str = ""
    
    @property
    def percent_complete(self) -> float:
        """Calculate percentage complete."""
        if self.total_epochs > 0:
            return (self.epoch / self.total_epochs) * 100
        return 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.status.value,
            "epoch": self.epoch,
            "total_epochs": self.total_epochs,
            "step": self.step,
            "total_steps": self.total_steps,
            "loss": self.loss,
            "val_loss": self.val_loss,
            "learning_rate": self.learning_rate,
            "elapsed_seconds": self.elapsed_seconds,
            "estimated_remaining_seconds": self.estimated_remaining_seconds,
            "samples_per_second": self.samples_per_second,
            "percent_complete": self.percent_complete,
            "checkpoints_saved": self.checkpoints_saved,
            "last_checkpoint_path": str(self.last_checkpoint_path) if self.last_checkpoint_path else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "message": self.message
        }


@dataclass
class TrainingConfig:
    """Configuration for training."""
    
    # Data paths
    metadata_path: Path
    audio_dir: Path
    cache_dir: Path
    output_dir: Path
    config_path: Path
    
    # Model settings
    voice_name: str = "kuiper"
    sample_rate: int = 22050
    espeak_voice: str = "en-us"
    
    # Training parameters
    batch_size: int = 32
    max_epochs: int = 2000
    learning_rate: float = 0.0001
    checkpoint_interval: int = 100
    validation_split: float = 0.1
    
    # Optional
    pretrained_checkpoint: Optional[Path] = None
    resume_checkpoint: Optional[Path] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metadata_path": str(self.metadata_path),
            "audio_dir": str(self.audio_dir),
            "cache_dir": str(self.cache_dir),
            "output_dir": str(self.output_dir),
            "config_path": str(self.config_path),
            "voice_name": self.voice_name,
            "sample_rate": self.sample_rate,
            "espeak_voice": self.espeak_voice,
            "batch_size": self.batch_size,
            "max_epochs": self.max_epochs,
            "learning_rate": self.learning_rate,
            "checkpoint_interval": self.checkpoint_interval,
            "validation_split": self.validation_split,
            "pretrained_checkpoint": str(self.pretrained_checkpoint) if self.pretrained_checkpoint else None,
            "resume_checkpoint": str(self.resume_checkpoint) if self.resume_checkpoint else None,
        }


class TrainingCallback:
    """Base class for training callbacks."""
    
    def on_training_start(self, config: TrainingConfig) -> None:
        """Called when training starts."""
        pass
    
    def on_epoch_start(self, epoch: int) -> None:
        """Called at the start of each epoch."""
        pass
    
    def on_epoch_end(self, epoch: int, loss: float, val_loss: Optional[float]) -> None:
        """Called at the end of each epoch."""
        pass
    
    def on_step(self, step: int, loss: float) -> None:
        """Called after each training step."""
        pass
    
    def on_checkpoint_saved(self, path: Path) -> None:
        """Called when a checkpoint is saved."""
        pass
    
    def on_training_end(self, success: bool, message: str) -> None:
        """Called when training ends."""
        pass
    
    def on_error(self, error: Exception) -> None:
        """Called when an error occurs."""
        pass


class ProgressCallback(TrainingCallback):
    """Callback that maintains progress state and notifies listeners."""
    
    def __init__(
        self,
        total_epochs: int,
        on_progress: Optional[Callable[[TrainingProgress], None]] = None
    ):
        self.total_epochs = total_epochs
        self.on_progress = on_progress
        self._progress = TrainingProgress(
            status=TrainingStatus.IDLE,
            epoch=0,
            total_epochs=total_epochs,
            step=0,
            total_steps=0,
            loss=0.0,
            val_loss=None,
            learning_rate=0.0001,
            elapsed_seconds=0,
            estimated_remaining_seconds=0,
            samples_per_second=0,
            checkpoints_saved=0,
            last_checkpoint_path=None,
            started_at=None
        )
        self._start_time: Optional[float] = None
        self._loss_history: List[float] = []
    
    @property
    def progress(self) -> TrainingProgress:
        """Get current progress."""
        return self._progress
    
    def _notify(self) -> None:
        """Notify listeners of progress update."""
        if self.on_progress:
            try:
                self.on_progress(self._progress)
            except Exception as e:
                logger.warning(f"Progress callback error: {e}")
    
    def _update_time_estimates(self) -> None:
        """Update elapsed and remaining time estimates."""
        if self._start_time:
            self._progress.elapsed_seconds = time.time() - self._start_time
            
            if self._progress.epoch > 0:
                seconds_per_epoch = self._progress.elapsed_seconds / self._progress.epoch
                remaining_epochs = self._progress.total_epochs - self._progress.epoch
                self._progress.estimated_remaining_seconds = seconds_per_epoch * remaining_epochs
    
    def on_training_start(self, config: TrainingConfig) -> None:
        self._start_time = time.time()
        self._progress.status = TrainingStatus.TRAINING
        self._progress.started_at = datetime.now()
        self._progress.message = "Training started"
        logger.info("Training started")
        self._notify()
    
    def on_epoch_start(self, epoch: int) -> None:
        self._progress.epoch = epoch
        self._update_time_estimates()
        self._notify()
    
    def on_epoch_end(self, epoch: int, loss: float, val_loss: Optional[float]) -> None:
        self._progress.epoch = epoch
        self._progress.loss = loss
        self._progress.val_loss = val_loss
        self._loss_history.append(loss)
        self._update_time_estimates()
        self._progress.message = f"Epoch {epoch}/{self.total_epochs} - Loss: {loss:.4f}"
        logger.info(f"Epoch {epoch}/{self.total_epochs} - Loss: {loss:.4f}" + 
                   (f" - Val Loss: {val_loss:.4f}" if val_loss else ""))
        self._notify()
    
    def on_step(self, step: int, loss: float) -> None:
        self._progress.step = step
        self._progress.loss = loss
        self._update_time_estimates()
    
    def on_checkpoint_saved(self, path: Path) -> None:
        self._progress.checkpoints_saved += 1
        self._progress.last_checkpoint_path = path
        self._progress.message = f"Checkpoint saved: {path.name}"
        logger.info(f"Checkpoint saved: {path}")
        self._notify()
    
    def on_training_end(self, success: bool, message: str) -> None:
        self._progress.status = TrainingStatus.COMPLETED if success else TrainingStatus.FAILED
        self._progress.message = message
        self._update_time_estimates()
        logger.info(f"Training {'completed' if success else 'failed'}: {message}")
        self._notify()
    
    def on_error(self, error: Exception) -> None:
        self._progress.status = TrainingStatus.FAILED
        self._progress.message = str(error)
        logger.error(f"Training error: {error}")
        self._notify()


class OutputParser:
    """Parse training output to extract progress information."""
    
    # Regex patterns for parsing PyTorch Lightning output
    EPOCH_PATTERN = re.compile(r'Epoch (\d+)')
    LOSS_PATTERN = re.compile(r'(?:loss|train_loss)[:\s]+([0-9.]+)', re.IGNORECASE)
    VAL_LOSS_PATTERN = re.compile(r'(?:val_loss|validation_loss)[:\s]+([0-9.]+)', re.IGNORECASE)
    STEP_PATTERN = re.compile(r'(?:step|batch)[:\s]+(\d+)', re.IGNORECASE)
    CHECKPOINT_PATTERN = re.compile(r'(?:Saving|saved).*checkpoint.*?([^\s]+\.ckpt)', re.IGNORECASE)
    
    def __init__(self, callback: ProgressCallback):
        self.callback = callback
        self.current_epoch = 0
        self.current_loss = 0.0
        self.current_val_loss: Optional[float] = None
    
    def parse_line(self, line: str) -> None:
        """Parse a single line of output."""
        # Check for epoch
        epoch_match = self.EPOCH_PATTERN.search(line)
        if epoch_match:
            new_epoch = int(epoch_match.group(1))
            if new_epoch != self.current_epoch:
                if self.current_epoch > 0:
                    # End previous epoch
                    self.callback.on_epoch_end(
                        self.current_epoch,
                        self.current_loss,
                        self.current_val_loss
                    )
                self.current_epoch = new_epoch
                self.current_val_loss = None
                self.callback.on_epoch_start(new_epoch)
        
        # Check for loss
        loss_match = self.LOSS_PATTERN.search(line)
        if loss_match:
            try:
                self.current_loss = float(loss_match.group(1))
            except ValueError:
                pass
        
        # Check for validation loss
        val_loss_match = self.VAL_LOSS_PATTERN.search(line)
        if val_loss_match:
            try:
                self.current_val_loss = float(val_loss_match.group(1))
            except ValueError:
                pass
        
        # Check for step
        step_match = self.STEP_PATTERN.search(line)
        if step_match:
            try:
                step = int(step_match.group(1))
                self.callback.on_step(step, self.current_loss)
            except ValueError:
                pass
        
        # Check for checkpoint
        ckpt_match = self.CHECKPOINT_PATTERN.search(line)
        if ckpt_match:
            ckpt_path = Path(ckpt_match.group(1))
            self.callback.on_checkpoint_saved(ckpt_path)


class Trainer:
    """
    Manages TTS model training.
    
    Wraps the Piper training system with progress tracking,
    pause/resume capability, and WebSocket-compatible callbacks.
    """
    
    def __init__(self, piper_path: Optional[Path] = None):
        """
        Initialize the trainer.
        
        Args:
            piper_path: Path to the piper source directory
        """
        self.piper_path = piper_path
        self._status = TrainingStatus.IDLE
        self._config: Optional[TrainingConfig] = None
        self._progress_callback: Optional[ProgressCallback] = None
        self._training_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._message_queue: queue.Queue = queue.Queue()
    
    @property
    def status(self) -> TrainingStatus:
        """Get current training status."""
        return self._status
    
    @property
    def progress(self) -> Optional[TrainingProgress]:
        """Get current training progress."""
        if self._progress_callback:
            return self._progress_callback.progress
        return None
    
    def prepare(self, config: TrainingConfig) -> bool:
        """
        Prepare for training by validating configuration.
        
        Args:
            config: Training configuration
        
        Returns:
            True if preparation successful
        """
        self._config = config
        self._status = TrainingStatus.PREPARING
        
        # Validate paths
        if not config.metadata_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {config.metadata_path}")
        
        if not config.audio_dir.exists():
            raise FileNotFoundError(f"Audio directory not found: {config.audio_dir}")
        
        # Create directories
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        config.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Write voice config
        voice_config = {
            "audio": {"sample_rate": config.sample_rate},
            "espeak": {"voice": config.espeak_voice},
            "trainer": {
                "max_epochs": config.max_epochs,
                "val_check_interval": 0.5,
            }
        }
        
        with open(config.config_path, "w") as f:
            json.dump(voice_config, f, indent=2)
        
        logger.info(f"Training configuration prepared")
        logger.info(f"  Metadata: {config.metadata_path}")
        logger.info(f"  Audio dir: {config.audio_dir}")
        logger.info(f"  Output dir: {config.output_dir}")
        logger.info(f"  Batch size: {config.batch_size}")
        logger.info(f"  Max epochs: {config.max_epochs}")
        
        return True
    
    def start(
        self,
        config: TrainingConfig,
        on_progress: Optional[Callable[[TrainingProgress], None]] = None
    ) -> None:
        """
        Start training in a background thread.
        
        Args:
            config: Training configuration
            on_progress: Callback for progress updates
        """
        if self._status == TrainingStatus.TRAINING:
            raise RuntimeError("Training already in progress")
        
        self.prepare(config)
        
        self._progress_callback = ProgressCallback(
            total_epochs=config.max_epochs,
            on_progress=on_progress
        )
        
        self._stop_event.clear()
        self._pause_event.clear()
        
        self._training_thread = threading.Thread(
            target=self._training_loop,
            args=(config,),
            daemon=True,
            name="TrainingThread"
        )
        self._training_thread.start()
        logger.info("Training thread started")
    
    def _training_loop(self, config: TrainingConfig) -> None:
        """Main training loop (runs in background thread)."""
        try:
            self._status = TrainingStatus.TRAINING
            self._progress_callback.on_training_start(config)
            
            # Build command-line arguments for piper training
            args = self._build_training_args(config)
            
            # Add piper to path
            if self.piper_path:
                piper_src = self.piper_path / "src"
                if piper_src.exists():
                    if str(piper_src) not in sys.path:
                        sys.path.insert(0, str(piper_src))
                    logger.info(f"Added piper to path: {piper_src}")
            
            # Import and run piper training
            self._run_piper_training(args, config)
            
            self._progress_callback.on_training_end(True, "Training completed successfully")
            self._status = TrainingStatus.COMPLETED
            
        except Exception as e:
            logger.exception(f"Training failed: {e}")
            self._progress_callback.on_error(e)
            self._status = TrainingStatus.FAILED
    
    def _build_training_args(self, config: TrainingConfig) -> List[str]:
        """Build command-line arguments for piper training."""
        args = [
            "train.py", "fit",
            f"--data.voice_name={config.voice_name}",
            f"--data.csv_path={config.metadata_path}",
            f"--data.audio_dir={config.audio_dir}",
            f"--data.espeak_voice={config.espeak_voice}",
            f"--model.sample_rate={config.sample_rate}",
            f"--data.cache_dir={config.cache_dir}",
            f"--data.config_path={config.config_path}",
            f"--data.batch_size={config.batch_size}",
            f"--trainer.default_root_dir={config.output_dir}",
            f"--trainer.max_epochs={config.max_epochs}",
        ]
        
        # Add checkpoint if provided
        if config.resume_checkpoint and config.resume_checkpoint.exists():
            args.append(f"--ckpt_path={config.resume_checkpoint}")
            args.append("--weights_only=true")
            logger.info(f"Resuming from checkpoint: {config.resume_checkpoint}")
        elif config.pretrained_checkpoint and config.pretrained_checkpoint.exists():
            args.append(f"--ckpt_path={config.pretrained_checkpoint}")
            args.append("--weights_only=true")
            logger.info(f"Using pretrained checkpoint: {config.pretrained_checkpoint}")
        
        # Add GPU settings
        args.extend([
            "--trainer.accelerator=auto",
            "--trainer.devices=1",
        ])
        
        logger.info(f"Training command: {' '.join(args)}")
        
        return args
    
    def _run_piper_training(self, args: List[str], config: TrainingConfig) -> None:
        """Run the piper training process."""
        import pathlib
        import torch
        
        # Required for loading checkpoints
        torch.serialization.add_safe_globals([pathlib.PosixPath])
        
        # Set sys.argv for LightningCLI
        original_argv = sys.argv
        sys.argv = args
        
        # Create output parser to extract progress
        parser = OutputParser(self._progress_callback)
        
        # Capture stdout to parse progress
        class OutputCapture(io.StringIO):
            def __init__(self, parser, original_stdout):
                super().__init__()
                self.parser = parser
                self.original = original_stdout
            
            def write(self, s):
                self.original.write(s)
                for line in s.split('\n'):
                    if line.strip():
                        self.parser.parse_line(line)
                return len(s)
            
            def flush(self):
                self.original.flush()
        
        try:
            # Import piper training
            from piper.train.__main__ import main
            
            # Capture output for progress parsing
            original_stdout = sys.stdout
            sys.stdout = OutputCapture(parser, original_stdout)
            
            try:
                main()
            finally:
                sys.stdout = original_stdout
                
        finally:
            sys.argv = original_argv
    
    def pause(self) -> None:
        """Pause training."""
        if self._status == TrainingStatus.TRAINING:
            self._pause_event.set()
            self._status = TrainingStatus.PAUSED
            logger.info("Training paused")
    
    def resume(self) -> None:
        """Resume training."""
        if self._status == TrainingStatus.PAUSED:
            self._pause_event.clear()
            self._status = TrainingStatus.TRAINING
            logger.info("Training resumed")
    
    def stop(self) -> None:
        """Stop training."""
        logger.info("Stopping training...")
        self._stop_event.set()
        self._pause_event.set()  # Unblock if paused
        
        if self._training_thread:
            self._training_thread.join(timeout=30)
            if self._training_thread.is_alive():
                logger.warning("Training thread did not stop gracefully")
        
        self._status = TrainingStatus.CANCELLED
        logger.info("Training stopped")
    
    def export_onnx(
        self,
        checkpoint_path: Path,
        output_path: Path
    ) -> Path:
        """
        Export a trained checkpoint to ONNX format.
        
        Args:
            checkpoint_path: Path to the training checkpoint
            output_path: Path for the output ONNX file
        
        Returns:
            Path to the exported ONNX file
        """
        logger.info(f"Exporting checkpoint to ONNX: {checkpoint_path} -> {output_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add piper to path
        if self.piper_path:
            piper_src = self.piper_path / "src"
            if piper_src.exists():
                if str(piper_src) not in sys.path:
                    sys.path.insert(0, str(piper_src))
        
        from piper.train.export_onnx import main as export_main
        
        original_argv = sys.argv
        sys.argv = [
            "export_onnx.py",
            f"--checkpoint={checkpoint_path}",
            f"--output-file={output_path}"
        ]
        
        try:
            export_main()
            logger.info(f"Successfully exported to: {output_path}")
        finally:
            sys.argv = original_argv
        
        return output_path


def create_trainer(piper_path: Optional[Path] = None) -> Trainer:
    """
    Create a trainer instance.
    
    Args:
        piper_path: Path to piper source directory
    
    Returns:
        Configured Trainer instance
    """
    return Trainer(piper_path)
