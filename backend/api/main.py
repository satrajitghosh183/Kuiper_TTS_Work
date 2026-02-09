# Kuiper TTS API Server
# FastAPI server for the Kuiper TTS desktop application

import asyncio
import json
import os
import sys
import logging
import logging.handlers
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager
from time import time

# Add parent directories to path for imports FIRST (before any local imports)
_current_dir = Path(__file__).parent.resolve()
_backend_dir = _current_dir.parent
_project_dir = _backend_dir.parent

if str(_project_dir) not in sys.path:
    sys.path.insert(0, str(_project_dir))
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# NOW import configuration (after path is set up)
from core.config import get_settings, get_project_root, get_recordings_dir, get_data_dir

# Configure logging based on settings
settings = get_settings()
log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

# Update project dir from settings if available
_project_dir = get_project_root()

# Create logs directory if log file is specified
if settings.log_file:
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logging.basicConfig(
        level=log_level,
        handlers=[handler, logging.StreamHandler()],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger('kuiper.api')

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi import Body
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

# Import from core modules using relative paths
from core import (
    KuiperConfig,
    SAMPLE_RATE,
    DEFAULT_BATCH_SIZE,
    format_duration,
)
from core.system_analyzer import SystemAnalyzer, SystemReport
from core.audio_processor import AudioProcessor, AudioInfo, AudioDeviceInfo
from core.data_preparer import DataPreparer, DatasetInfo, TextScript
from core.trainer import Trainer, TrainingConfig, TrainingProgress, TrainingStatus
from core.espeak import ESpeakNG


# Global state
class AppState:
    """Application state container."""
    
    def __init__(self):
        self.config = KuiperConfig()
        self.config.recordings_dir = get_recordings_dir()
        self.config.root_dir = get_data_dir()
        self.system_analyzer = SystemAnalyzer()
        self.audio_processor = AudioProcessor(SAMPLE_RATE)
        self.trainer: Optional[Trainer] = None
        self.training_clients: List[WebSocket] = []
        self.system_report: Optional[SystemReport] = None
        self.scripts_cache: dict = {}  # Cache for loaded scripts
        self.rate_limit_store: dict = {}  # Simple in-memory rate limiting


state = AppState()

# Initialize eSpeak NG (graceful fallback if not available)
espeak = ESpeakNG()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Kuiper TTS API server...")
    try:
        state.system_report = state.system_analyzer.analyze()
        logger.info(f"System analysis complete. Can train: {state.system_report.can_train}")
        logger.info(f"Training backend: {state.system_report.training_backend}")
    except Exception as e:
        logger.error(f"Failed to analyze system: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Kuiper TTS API server...")
    if state.trainer and state.trainer.status == TrainingStatus.TRAINING:
        logger.info("Stopping active training...")
        state.trainer.stop()


app = FastAPI(
    title="Kuiper TTS API",
    description="API for Kuiper TTS voice training",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Security: Trusted Host Middleware (only in production)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost"]
    )

# CORS configuration - use settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Simple rate limiting middleware."""
    if settings.is_production and settings.rate_limit_per_minute > 0:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time()
        minute_ago = current_time - 60
        
        # Initialize store for this IP if needed
        if client_ip not in state.rate_limit_store:
            state.rate_limit_store[client_ip] = []
        
        # Clean old entries for this IP (older than 1 minute)
        state.rate_limit_store[client_ip] = [
            t for t in state.rate_limit_store[client_ip] if t > minute_ago
        ]
        
        # Check rate limit
        if len(state.rate_limit_store[client_ip]) >= settings.rate_limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again later."}
            )
        
        # Record request
        state.rate_limit_store[client_ip].append(current_time)
    
    response = await call_next(request)
    return response


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation error", "errors": exc.errors()}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    error_detail = str(exc) if settings.debug else "An internal error occurred"
    return JSONResponse(
        status_code=500,
        content={"detail": error_detail}
    )


# ============================================================================
# Request/Response Models
# ============================================================================

class SystemCheckResponse(BaseModel):
    """System check response."""
    
    can_train: bool
    training_backend: str
    gpu_name: Optional[str]
    gpu_vram_gb: Optional[float]
    ram_total_gb: float
    ram_available_gb: float
    storage_free_gb: float
    python_version: str
    cuda_available: bool
    mps_available: bool
    warnings: List[str]
    errors: List[str]


class TrainingEstimateRequest(BaseModel):
    """Request for training time estimate."""
    
    sample_count: int = Field(ge=1, le=10000)


class TrainingEstimateResponse(BaseModel):
    """Training time estimate response."""
    
    estimated_time: str
    recommended_batch_size: int
    recommended_epochs: int


class AudioDeviceResponse(BaseModel):
    """Audio device information."""
    
    device_id: int
    name: str
    channels: int
    sample_rate: float
    is_default: bool


class AudioTestRequest(BaseModel):
    """Request for audio test."""
    
    device_id: Optional[int] = None
    duration_seconds: float = Field(default=2.0, ge=0.5, le=10.0)


class AudioTestResponse(BaseModel):
    """Audio test response."""
    
    success: bool
    peak_level: float
    rms_level: float
    db_level: float
    is_clipping: bool
    recommended_gain: float
    error: Optional[str] = None


class RecordingListItem(BaseModel):
    """Recording list item."""
    
    filename: str
    text: str
    duration_seconds: float
    is_valid: bool
    error: Optional[str] = None


class RecordingProgressResponse(BaseModel):
    """Recording progress response."""
    
    script_name: str
    recorded: int
    total: int
    remaining: int
    percent: int


class ScriptResponse(BaseModel):
    """Text script response."""
    
    name: str
    path: str
    lines: List[str]
    line_count: int


class PrepareTrainingRequest(BaseModel):
    """Request to prepare training data."""
    
    recordings_dir: str
    output_dir: str
    voice_name: str = "kuiper"
    script_files: Optional[List[str]] = None


class PrepareTrainingResponse(BaseModel):
    """Response from preparing training data."""
    
    success: bool
    total_recordings: int
    valid_recordings: int
    invalid_recordings: int
    total_duration_seconds: float
    metadata_path: str
    audio_dir: str
    errors: List[str]
    warnings: List[str]


class StartTrainingRequest(BaseModel):
    """Request to start training."""
    
    metadata_path: str
    audio_dir: str
    output_dir: str
    voice_name: str = "kuiper"
    espeak_voice: str = "en-us"
    batch_size: Optional[int] = None
    max_epochs: int = 2000
    pretrained_checkpoint: Optional[str] = None


class TrainingStatusResponse(BaseModel):
    """Training status response."""
    
    status: str
    epoch: int
    total_epochs: int
    loss: float
    val_loss: Optional[float]
    percent_complete: float
    elapsed_seconds: float
    estimated_remaining_seconds: float
    message: str


class SynthesizeRequest(BaseModel):
    """Request to synthesize speech."""
    
    text: str
    model_path: Optional[str] = None


class SynthesizeResponse(BaseModel):
    """Response from speech synthesis."""
    
    success: bool
    audio_path: Optional[str] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None


class ExportVoiceRequest(BaseModel):
    """Request to export voice model."""
    
    checkpoint_path: str
    output_path: str
    voice_name: str


# ============================================================================
# System Routes
# ============================================================================

@app.get("/api/system/check", response_model=SystemCheckResponse)
async def system_check():
    """Check system capabilities for training."""
    try:
        if state.system_report is None:
            state.system_report = state.system_analyzer.analyze()
        
        report = state.system_report
        
        return SystemCheckResponse(
            can_train=report.can_train,
            training_backend=report.training_backend,
            gpu_name=report.gpu.name if report.gpu else None,
            gpu_vram_gb=report.gpu.vram_total_gb if report.gpu else None,
            ram_total_gb=report.memory.total_gb,
            ram_available_gb=report.memory.available_gb,
            storage_free_gb=report.storage.free_gb,
            python_version=report.python_version,
            cuda_available=report.cuda_available,
            mps_available=report.mps_available,
            warnings=report.warnings,
            errors=report.errors
        )
    except Exception as e:
        logger.error(f"System check failed: {e}")
        raise HTTPException(500, f"System check failed: {e}")


@app.post("/api/system/estimate", response_model=TrainingEstimateResponse)
async def training_estimate(request: TrainingEstimateRequest):
    """Estimate training time for a given sample count."""
    try:
        if state.system_report is None:
            state.system_report = state.system_analyzer.analyze()
        
        report = state.system_report
        
        if report.estimates is None:
            raise HTTPException(500, "Could not calculate estimates")
        
        # Interpolate time based on sample count
        base_times = {
            100: 30 * 60,    # 30 minutes
            500: 150 * 60,   # 2.5 hours
            1000: 300 * 60,  # 5 hours
        }
        
        # Simple linear interpolation
        if request.sample_count <= 100:
            estimated_seconds = base_times[100] * (request.sample_count / 100)
        elif request.sample_count <= 500:
            ratio = (request.sample_count - 100) / 400
            estimated_seconds = base_times[100] + ratio * (base_times[500] - base_times[100])
        elif request.sample_count <= 1000:
            ratio = (request.sample_count - 500) / 500
            estimated_seconds = base_times[500] + ratio * (base_times[1000] - base_times[500])
        else:
            # Extrapolate for larger counts
            estimated_seconds = base_times[1000] * (request.sample_count / 1000)
        
        return TrainingEstimateResponse(
            estimated_time=format_duration(estimated_seconds),
            recommended_batch_size=report.estimates.recommended_batch_size,
            recommended_epochs=report.estimates.recommended_epochs
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Training estimate failed: {e}")
        raise HTTPException(500, f"Training estimate failed: {e}")


# ============================================================================
# Scripts Routes
# ============================================================================

@app.get("/api/scripts", response_model=List[ScriptResponse])
async def list_scripts(
    directory: Optional[str] = Query(None, description="Directory to search for scripts")
):
    """List available text script files."""
    try:
        search_dir = Path(directory) if directory else _project_dir
        
        if not search_dir.exists():
            return []
        
        scripts = []
        for txt_file in search_dir.glob("*.txt"):
            try:
                script = TextScript.from_file(txt_file)
                scripts.append(ScriptResponse(
                    name=script.name,
                    path=str(txt_file),
                    lines=script.lines,
                    line_count=len(script.lines)
                ))
            except Exception as e:
                logger.warning(f"Failed to load script {txt_file}: {e}")
        
        return scripts
    except Exception as e:
        logger.error(f"Failed to list scripts: {e}")
        raise HTTPException(500, f"Failed to list scripts: {e}")


@app.get("/api/scripts/{script_name}", response_model=ScriptResponse)
async def get_script(script_name: str):
    """Get a specific script by name."""
    try:
        # Security: Prevent path traversal
        script_name = Path(script_name).name  # Only get the filename
        if ".." in script_name or "/" in script_name or "\\" in script_name:
            raise HTTPException(400, "Invalid script name")
        
        # Search for the script file
        script_path = _project_dir / f"{script_name}.txt"
        
        if not script_path.exists():
            # Try without extension
            script_path = _project_dir / script_name
            if not script_path.exists():
                raise HTTPException(404, f"Script not found: {script_name}")
        
        # Security: Ensure path is within project directory
        try:
            script_path.resolve().relative_to(_project_dir.resolve())
        except ValueError:
            raise HTTPException(400, "Invalid script path")
        
        script = TextScript.from_file(script_path)
        return ScriptResponse(
            name=script.name,
            path=str(script_path),
            lines=script.lines,
            line_count=len(script.lines)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get script: {e}")
        raise HTTPException(500, f"Failed to get script: {e}")


# ============================================================================
# Audio Routes
# ============================================================================

@app.get("/api/audio/devices", response_model=List[AudioDeviceResponse])
async def list_audio_devices():
    """List available audio input devices."""
    try:
        devices = state.audio_processor.list_devices()
        
        if not devices:
            logger.warning("No audio input devices found. Make sure:")
            logger.warning("1. sounddevice is installed: pip install sounddevice")
            logger.warning("2. Microphone permissions are granted (macOS: System Settings > Privacy & Security > Microphone)")
            logger.warning("3. A microphone is connected and working")
        
        return [
            AudioDeviceResponse(
                device_id=d.device_id,
                name=d.name,
                channels=d.channels,
                sample_rate=d.sample_rate,
                is_default=d.is_default
            )
            for d in devices
        ]
    except Exception as e:
        logger.error(f"Failed to list audio devices: {e}")
        # Return empty list instead of raising error, so UI can show helpful message
        return []


@app.post("/api/audio/test", response_model=AudioTestResponse)
async def test_audio_device(request: AudioTestRequest):
    """Test an audio device."""
    try:
        success, levels, error = state.audio_processor.test_device(
            device_id=request.device_id,
            duration_seconds=request.duration_seconds
        )
        
        recommended_gain, _ = state.audio_processor.get_recommended_gain(
            device_id=request.device_id,
            test_duration=request.duration_seconds
        )
        
        return AudioTestResponse(
            success=success,
            peak_level=levels.peak,
            rms_level=levels.rms,
            db_level=levels.db,
            is_clipping=levels.is_clipping,
            recommended_gain=recommended_gain,
            error=error
        )
    except Exception as e:
        logger.error(f"Audio test failed: {e}")
        raise HTTPException(500, f"Audio test failed: {e}")


@app.post("/api/recording/save")
async def save_recording(
    audio_file: UploadFile = File(...),
    filename: str = "",
    gain: float = 1.0,
    normalize: bool = False
):
    """Save an uploaded audio recording. Accepts WAV, WebM, MP4, and other formats."""
    try:
        # Validate file size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        if audio_file.size and audio_file.size > max_size_bytes:
            raise HTTPException(
                413,
                f"File too large. Maximum size is {settings.max_upload_size_mb}MB"
            )
        
        if not filename:
            filename = audio_file.filename or "recording.wav"
        
        # Security: Prevent path traversal attacks
        filename = Path(filename).name  # Only get the filename, not the path
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        
        # Ensure .wav extension
        if not filename.lower().endswith('.wav'):
            filename = Path(filename).stem + '.wav'
        
        # Determine output path
        recordings_dir = state.config.recordings_dir
        recordings_dir.mkdir(parents=True, exist_ok=True)
        output_path = recordings_dir / filename
        
        # Security: Ensure output path is within recordings directory
        try:
            output_path.resolve().relative_to(recordings_dir.resolve())
        except ValueError:
            raise HTTPException(400, "Invalid file path")
        
        # Read audio data with size limit
        audio_data = await audio_file.read()
        
        # Check actual size after reading
        if len(audio_data) > max_size_bytes:
            raise HTTPException(
                413,
                f"File too large. Maximum size is {settings.max_upload_size_mb}MB"
            )
        
        if len(audio_data) == 0:
            return {
                "success": False,
                "path": str(output_path),
                "duration_seconds": 0,
                "peak_amplitude": 0,
                "rms_level": 0,
                "error": "Empty audio data received"
            }
        
        # Check if it's already a WAV file
        is_wav = len(audio_data) >= 12 and audio_data[:4] == b'RIFF' and b'WAVE' in audio_data[:12]
        
        if is_wav:
            # Direct WAV file - save as-is
            audio_info = state.audio_processor.save_recording(
                audio_data=audio_data,
                output_path=output_path,
                gain=gain,
                normalize=normalize
            )
        else:
            # Convert from WebM/MP4/etc to WAV using librosa
            try:
                import librosa
                import numpy as np
                import tempfile
                import wave
                
                # Save to temp file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.tmp') as tmp:
                    tmp.write(audio_data)
                    tmp_path = Path(tmp.name)
                
                try:
                    # Load with librosa (handles many formats)
                    y, sr = librosa.load(str(tmp_path), sr=22050, mono=True)
                    
                    # Apply gain
                    if gain != 1.0:
                        y = y * gain
                        y = np.clip(y, -1.0, 1.0)
                    
                    # Convert to int16
                    y_int16 = (y * 32767).astype(np.int16)
                    
                    # Save as WAV
                    with wave.open(str(output_path), 'wb') as wf:
                        wf.setnchannels(1)  # Mono
                        wf.setsampwidth(2)  # 16-bit
                        wf.setframerate(22050)
                        wf.writeframes(y_int16.tobytes())
                    
                    # Analyze the saved file
                    audio_info = state.audio_processor.analyze_file(output_path)
                    
                    # Normalize if requested
                    if normalize and audio_info.is_valid:
                        audio_info = state.audio_processor.normalize_audio(output_path, output_path)
                    
                finally:
                    # Clean up temp file
                    if tmp_path.exists():
                        tmp_path.unlink()
                        
            except ImportError:
                return {
                    "success": False,
                    "path": str(output_path),
                    "duration_seconds": 0,
                    "peak_amplitude": 0,
                    "rms_level": 0,
                    "error": "librosa not installed - cannot convert audio formats"
                }
            except Exception as e:
                logger.error(f"Failed to convert audio: {e}")
                return {
                    "success": False,
                    "path": str(output_path),
                    "duration_seconds": 0,
                    "peak_amplitude": 0,
                    "rms_level": 0,
                    "error": f"Failed to convert audio: {str(e)}"
                }
        
        logger.info(f"Saved recording: {output_path} ({audio_info.duration_seconds:.2f}s)")
        
        return {
            "success": audio_info.is_valid,
            "path": str(output_path),
            "duration_seconds": audio_info.duration_seconds,
            "peak_amplitude": audio_info.peak_amplitude,
            "rms_level": audio_info.rms_level,
            "error": audio_info.error
        }
    except Exception as e:
        logger.error(f"Failed to save recording: {e}")
        return {
            "success": False,
            "path": "",
            "duration_seconds": 0,
            "peak_amplitude": 0,
            "rms_level": 0,
            "error": str(e)
        }


@app.get("/api/recording/list", response_model=List[RecordingListItem])
async def list_recordings():
    """List all recordings."""
    try:
        recordings_dir = state.config.recordings_dir
        
        if not recordings_dir.exists():
            return []
        
        # Get data preparer to match recordings with text
        preparer = DataPreparer(recordings_dir, state.config.root_dir)
        groups = preparer.scan_recordings()
        
        items = []
        for script_name, recordings in groups.items():
            script_path = preparer.find_script_file(script_name)
            
            if script_path:
                script = TextScript.from_file(script_path)
                
                for index, wav_path in recordings:
                    text_index = index - 1
                    text = script.lines[text_index] if 0 <= text_index < len(script.lines) else ""
                    
                    audio_info = state.audio_processor.analyze_file(wav_path)
                    
                    items.append(RecordingListItem(
                        filename=wav_path.name,
                        text=text,
                        duration_seconds=audio_info.duration_seconds,
                        is_valid=audio_info.is_valid,
                        error=audio_info.error
                    ))
            else:
                for index, wav_path in recordings:
                    audio_info = state.audio_processor.analyze_file(wav_path)
                    items.append(RecordingListItem(
                        filename=wav_path.name,
                        text="",
                        duration_seconds=audio_info.duration_seconds,
                        is_valid=audio_info.is_valid,
                        error=audio_info.error
                    ))
        
        return items
    except Exception as e:
        logger.error(f"Failed to list recordings: {e}")
        raise HTTPException(500, f"Failed to list recordings: {e}")


@app.get("/api/recording/download")
async def download_recordings():
    """Download all recordings as a ZIP file."""
    import zipfile
    import io
    from fastapi.responses import Response
    
    try:
        recordings_dir = state.config.recordings_dir
        
        if not recordings_dir.exists():
            raise HTTPException(404, "No recordings directory found")
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Get all WAV files
            for wav_file in recordings_dir.glob("*.wav"):
                try:
                    with open(wav_file, 'rb') as f:
                        zip_file.writestr(wav_file.name, f.read())
                except Exception as e:
                    logger.warning(f"Failed to add {wav_file.name} to ZIP: {e}")
                    continue
        
        zip_buffer.seek(0)
        
        if zip_buffer.tell() == 0:
            raise HTTPException(404, "No recordings found")
        
        return Response(
            content=zip_buffer.read(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=recordings_{int(time())}.zip"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create recordings ZIP: {e}")
        raise HTTPException(500, f"Failed to create recordings ZIP: {e}")


@app.get("/api/recording/progress", response_model=List[RecordingProgressResponse])
async def get_recording_progress():
    """Get recording progress for each script."""
    try:
        recordings_dir = state.config.recordings_dir
        
        # Find all script files in the project
        script_files = list(_project_dir.glob("*.txt"))
        
        if not script_files:
            return []
        
        preparer = DataPreparer(recordings_dir, state.config.root_dir)
        progress = preparer.get_recording_progress(script_files)
        
        return [
            RecordingProgressResponse(
                script_name=name,
                recorded=data["recorded"],
                total=data["total"],
                remaining=data["remaining"],
                percent=data["percent"]
            )
            for name, data in progress.items()
        ]
    except Exception as e:
        logger.error(f"Failed to get recording progress: {e}")
        raise HTTPException(500, f"Failed to get recording progress: {e}")


# ============================================================================
# Training Routes
# ============================================================================

@app.get("/api/training/scan")
async def scan_training_data(
    recordings_dir: Optional[str] = None,
    project_root: Optional[str] = None
):
    """Scan for existing recordings and text files."""
    try:
        # Use provided paths or defaults
        rec_dir = Path(recordings_dir) if recordings_dir else state.config.recordings_dir
        root_dir = Path(project_root) if project_root else _project_dir
        
        result = {
            "recordings_dir": str(rec_dir),
            "recordings_dir_exists": rec_dir.exists(),
            "recordings_count": 0,
            "text_files": [],
            "recordings": [],
            "warnings": []
        }
        
        # Scan for text files in project root
        text_files = list(root_dir.glob("*.txt"))
        result["text_files"] = [
            {
                "path": str(f),
                "name": f.stem,
                "line_count": len(TextScript.from_file(f).lines)
            }
            for f in text_files
        ]
        
        # Scan for recordings
        if rec_dir.exists():
            wav_files = list(rec_dir.glob("*.wav"))
            result["recordings_count"] = len(wav_files)
            
            # Try to match recordings with text files
            preparer = DataPreparer(rec_dir, root_dir)
            groups = preparer.scan_recordings()
            
            for script_name, recordings in groups.items():
                script_path = preparer.find_script_file(script_name)
                script = TextScript.from_file(script_path) if script_path else None
                
                for index, wav_path in recordings:
                    text_index = index - 1
                    text = script.lines[text_index] if script and 0 <= text_index < len(script.lines) else ""
                    
                    result["recordings"].append({
                        "filename": wav_path.name,
                        "path": str(wav_path),
                        "script_name": script_name,
                        "index": index,
                        "text": text,
                        "has_text": bool(text)
                    })
        else:
            result["warnings"].append(f"Recordings directory not found: {rec_dir}")
        
        return result
    except Exception as e:
        logger.error(f"Failed to scan training data: {e}")
        raise HTTPException(500, f"Failed to scan training data: {e}")


@app.post("/api/training/prepare", response_model=PrepareTrainingResponse)
async def prepare_training(request: PrepareTrainingRequest):
    """Prepare training data from recordings."""
    try:
        recordings_dir = Path(request.recordings_dir)
        output_dir = Path(request.output_dir)
        
        if not recordings_dir.exists():
            raise HTTPException(400, f"Recordings directory not found: {recordings_dir}")
        
        script_files = None
        if request.script_files:
            script_files = [Path(f) for f in request.script_files]
        else:
            # Auto-detect text files in project root if not provided
            project_root = recordings_dir.parent if recordings_dir.parent.exists() else _project_dir
            script_files = list(project_root.glob("*.txt"))
            if not script_files:
                # Try current working directory
                script_files = list(_project_dir.glob("*.txt"))
        
        preparer = DataPreparer(recordings_dir, output_dir)
        result = preparer.prepare_dataset(
            script_files=script_files,
            voice_name=request.voice_name
        )
        
        logger.info(f"Prepared {result.valid_recordings}/{result.total_recordings} recordings")
        
        return PrepareTrainingResponse(
            success=len(result.errors) == 0,
            total_recordings=result.total_recordings,
            valid_recordings=result.valid_recordings,
            invalid_recordings=result.invalid_recordings,
            total_duration_seconds=result.total_duration_seconds,
            metadata_path=str(result.metadata_path),
            audio_dir=str(result.audio_dir),
            errors=result.errors,
            warnings=result.warnings
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to prepare training data: {e}")
        raise HTTPException(500, f"Failed to prepare training data: {e}")


@app.post("/api/training/start")
async def start_training(request: StartTrainingRequest):
    """Start model training."""
    try:
        if state.trainer and state.trainer.status == TrainingStatus.TRAINING:
            raise HTTPException(400, "Training already in progress")
        
        # Determine batch size
        batch_size = request.batch_size
        if batch_size is None:
            if state.system_report and state.system_report.estimates:
                batch_size = state.system_report.estimates.recommended_batch_size
            else:
                batch_size = DEFAULT_BATCH_SIZE
        
        config = TrainingConfig(
            metadata_path=Path(request.metadata_path),
            audio_dir=Path(request.audio_dir),
            cache_dir=Path(request.output_dir) / "cache",
            output_dir=Path(request.output_dir),
            config_path=Path(request.output_dir) / f"{request.voice_name}.json",
            voice_name=request.voice_name,
            espeak_voice=request.espeak_voice,
            batch_size=batch_size,
            max_epochs=request.max_epochs,
            pretrained_checkpoint=Path(request.pretrained_checkpoint) if request.pretrained_checkpoint else None
        )
        
        # Create trainer
        piper_path = _project_dir / "piper1-gpl"
        state.trainer = Trainer(piper_path)
        
        # Define progress callback that broadcasts to WebSocket clients
        async def broadcast_progress(progress: TrainingProgress):
            disconnected = []
            for client in state.training_clients:
                try:
                    await client.send_json(progress.to_dict())
                except Exception as e:
                    logger.debug(f"Failed to send to client: {e}")
                    disconnected.append(client)
            
            # Remove disconnected clients
            for client in disconnected:
                if client in state.training_clients:
                    state.training_clients.remove(client)
        
        def on_progress(progress: TrainingProgress):
            # Run async broadcast in event loop
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(broadcast_progress(progress))
            except RuntimeError:
                # No running loop, ignore
                pass
        
        # Start training in background
        logger.info(f"Starting training with batch_size={batch_size}, epochs={request.max_epochs}")
        state.trainer.start(config, on_progress=on_progress)
        
        return {"success": True, "message": "Training started"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to start training: {e}")
        raise HTTPException(500, f"Failed to start training: {e}")


@app.get("/api/training/status", response_model=TrainingStatusResponse)
async def get_training_status():
    """Get current training status."""
    if state.trainer is None:
        return TrainingStatusResponse(
            status=TrainingStatus.IDLE.value,
            epoch=0,
            total_epochs=0,
            loss=0,
            val_loss=None,
            percent_complete=0,
            elapsed_seconds=0,
            estimated_remaining_seconds=0,
            message="No training in progress"
        )
    
    progress = state.trainer.progress
    if progress is None:
        return TrainingStatusResponse(
            status=state.trainer.status.value,
            epoch=0,
            total_epochs=0,
            loss=0,
            val_loss=None,
            percent_complete=0,
            elapsed_seconds=0,
            estimated_remaining_seconds=0,
            message=""
        )
    
    return TrainingStatusResponse(
        status=progress.status.value,
        epoch=progress.epoch,
        total_epochs=progress.total_epochs,
        loss=progress.loss,
        val_loss=progress.val_loss,
        percent_complete=progress.percent_complete,
        elapsed_seconds=progress.elapsed_seconds,
        estimated_remaining_seconds=progress.estimated_remaining_seconds,
        message=progress.message
    )


@app.post("/api/training/pause")
async def pause_training():
    """Pause training."""
    if state.trainer is None or state.trainer.status != TrainingStatus.TRAINING:
        raise HTTPException(400, "No training in progress")
    
    state.trainer.pause()
    logger.info("Training paused")
    return {"success": True, "message": "Training paused"}


@app.post("/api/training/stop")
async def stop_training():
    """Stop training."""
    if state.trainer is None:
        raise HTTPException(400, "No training in progress")
    
    state.trainer.stop()
    logger.info("Training stopped")
    return {"success": True, "message": "Training stopped"}


@app.websocket("/api/training/stream")
async def training_stream(websocket: WebSocket):
    """WebSocket endpoint for real-time training updates."""
    await websocket.accept()
    state.training_clients.append(websocket)
    logger.info(f"Training WebSocket client connected. Total clients: {len(state.training_clients)}")
    
    try:
        # Send current status immediately
        if state.trainer and state.trainer.progress:
            await websocket.send_json(state.trainer.progress.to_dict())
        
        # Keep connection open
        while True:
            try:
                # Wait for any message (ping/pong)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                # Echo back as pong
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("Training WebSocket client disconnected")
    finally:
        if websocket in state.training_clients:
            state.training_clients.remove(websocket)


# ============================================================================
# Voice Routes
# ============================================================================

@app.post("/api/voice/synthesize", response_model=SynthesizeResponse)
async def synthesize_voice(request: SynthesizeRequest):
    """Synthesize speech from text using trained model."""
    try:
        # Check for trained model
        model_path = Path(request.model_path) if request.model_path else None
        
        if model_path is None:
            # Try to find the latest exported model
            exports_dir = _project_dir / "exports"
            if exports_dir.exists():
                onnx_files = list(exports_dir.glob("*.onnx"))
                if onnx_files:
                    model_path = max(onnx_files, key=lambda p: p.stat().st_mtime)
        
        if model_path is None or not model_path.exists():
            return SynthesizeResponse(
                success=False,
                error="No trained model found. Please export your model first."
            )
        
        # Try to use piper for synthesis
        try:
            piper_src = _project_dir / "piper1-gpl" / "src"
            if piper_src.exists():
                sys.path.insert(0, str(piper_src))
            
            from piper import PiperVoice
            
            voice = PiperVoice.load(str(model_path))
            
            # Generate audio
            import wave
            import tempfile
            
            output_dir = _project_dir / "output"
            output_dir.mkdir(exist_ok=True)
            output_path = output_dir / "synthesized.wav"
            
            with wave.open(str(output_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(22050)
                
                for audio_bytes in voice.synthesize_stream_raw(request.text):
                    wav_file.writeframes(audio_bytes)
            
            # Get duration
            audio_info = state.audio_processor.analyze_file(output_path)
            
            return SynthesizeResponse(
                success=True,
                audio_path=str(output_path),
                duration_seconds=audio_info.duration_seconds
            )
            
        except ImportError as e:
            logger.warning(f"Piper not available for synthesis: {e}")
            return SynthesizeResponse(
                success=False,
                error="Voice synthesis requires piper to be installed"
            )
            
    except Exception as e:
        logger.error(f"Synthesis failed: {e}")
        return SynthesizeResponse(
            success=False,
            error=str(e)
        )


@app.post("/api/voice/export")
async def export_voice(request: ExportVoiceRequest):
    """Export trained model to ONNX format."""
    try:
        checkpoint_path = Path(request.checkpoint_path)
        output_path = Path(request.output_path)
        
        if not checkpoint_path.exists():
            raise HTTPException(400, f"Checkpoint not found: {checkpoint_path}")
        
        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        piper_path = _project_dir / "piper1-gpl"
        trainer = Trainer(piper_path)
        
        result_path = trainer.export_onnx(checkpoint_path, output_path)
        logger.info(f"Exported model to: {result_path}")
        
        return {
            "success": True,
            "onnx_path": str(result_path),
            "message": f"Model exported to {result_path}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(500, f"Export failed: {e}")


# ============================================================================
# Audio File Serving
# ============================================================================

@app.post("/api/voice/pronounce")
async def pronounce_text(
    text: str = Body(..., embed=True),
    voice: Optional[str] = Body(None, embed=True)
):
    """Generate pronunciation audio using eSpeak NG."""
    if not espeak.is_available():
        raise HTTPException(
            status_code=503, 
            detail="eSpeak NG not available. Please install espeak-ng."
        )
    
    try:
        output_path = espeak.generate_pronunciation(text, voice=voice)
        
        # Return file
        return FileResponse(
            output_path,
            media_type='audio/wav',
            filename='pronunciation.wav',
            background=lambda: output_path.unlink() if output_path.exists() else None  # Cleanup after send
        )
    except Exception as e:
        logger.error(f"Pronunciation failed: {e}")
        raise HTTPException(500, f"Failed to generate pronunciation: {e}")


@app.get("/api/voice/audio/{filename}")
async def get_audio_file(filename: str):
    """Serve synthesized audio files."""
    try:
        # Security: Prevent path traversal
        filename = Path(filename).name  # Only get the filename
        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(400, "Invalid filename")
        
        # Try output directory first
        output_dir = _project_dir / "output"
        audio_path = output_dir / filename
        
        # Security: Ensure path is within allowed directories
        if audio_path.exists():
            try:
                audio_path.resolve().relative_to(output_dir.resolve())
            except ValueError:
                raise HTTPException(400, "Invalid file path")
        else:
            # Try recordings directory
            recordings_dir = state.config.recordings_dir
            audio_path = recordings_dir / filename
            if audio_path.exists():
                try:
                    audio_path.resolve().relative_to(recordings_dir.resolve())
                except ValueError:
                    raise HTTPException(400, "Invalid file path")
            
        if not audio_path.exists():
            raise HTTPException(404, f"Audio file not found: {filename}")
        
        return FileResponse(
            path=str(audio_path),
            media_type="audio/wav",
            filename=filename
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve audio file: {e}")
        raise HTTPException(500, f"Failed to serve audio file: {e}")


# ============================================================================
# Health Check
# ============================================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint with detailed status."""
    health_status = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.environment,
        "training_active": state.trainer is not None and state.trainer.status == TrainingStatus.TRAINING,
        "system_analyzed": state.system_report is not None,
    }
    
    # Add system info if available
    if state.system_report:
        health_status["can_train"] = state.system_report.can_train
        health_status["training_backend"] = state.system_report.training_backend
    
    # Check critical paths
    try:
        recordings_dir = state.config.recordings_dir
        health_status["recordings_dir_accessible"] = recordings_dir.exists() or recordings_dir.parent.exists()
    except Exception:
        health_status["recordings_dir_accessible"] = False
    
    # Determine overall health
    if not health_status.get("recordings_dir_accessible", True):
        health_status["status"] = "degraded"
    
    return health_status


# ============================================================================
# Run Server
# ============================================================================

def run_server(host: str = "127.0.0.1", port: int = 8765):
    """Run the API server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()
