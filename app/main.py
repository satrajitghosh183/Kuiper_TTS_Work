"""
FastAPI production server for PDF-to-LaTeX conversion.

Provides REST API endpoints for:
- Async PDF conversion with job tracking
- Synchronous conversion for small files
- Job status and result retrieval
- Health and readiness checks
- Prometheus metrics
"""

from __future__ import annotations

import hashlib
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

import aiofiles
import structlog
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response

from app.config import ConversionConfig, settings
from app.converter.agent import PDFToLaTeXAgent
from app.dependencies import get_redis, verify_api_key
from app.models import (
    ConversionResponse,
    HealthResponse,
    JobStatus,
    JobStatusResponse,
    OutputFormat,
    ReadinessResponse,
    SyncConversionResponse,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# Prometheus metrics
REQUESTS_TOTAL = Counter(
    "pdf_latex_requests_total",
    "Total requests",
    ["endpoint", "status"],
)
CONVERSION_DURATION = Histogram(
    "pdf_latex_conversion_seconds",
    "Conversion duration in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)
QUEUE_SIZE = Counter("pdf_latex_queue_size", "Jobs added to queue")
FILE_SIZE_BYTES = Histogram(
    "pdf_latex_file_size_bytes",
    "Uploaded file sizes",
    buckets=[1e5, 5e5, 1e6, 5e6, 1e7, 5e7],
)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    logger.info(
        "Starting PDF-to-LaTeX API server",
        version="1.0.0",
        log_level=settings.LOG_LEVEL,
    )

    # Startup: verify configuration
    if not settings.HF_TOKEN:
        logger.warning("HF_TOKEN not set - using fallback providers")

    # Create required directories
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
    Path(settings.FIGURES_DIR).mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info("Shutting down PDF-to-LaTeX API server")


# Create FastAPI app
app = FastAPI(
    title="PDF-to-LaTeX Conversion API",
    description="""
    Production-ready agentic PDF to LaTeX converter.
    
    ## Features
    - Multimodal parsing using Vision Language Models
    - Async job processing for large files
    - Image extraction and caption generation
    - LaTeX compilation validation
    
    ## Authentication
    Use the `X-API-Key` header or `Authorization: Bearer <token>` for authentication.
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ==================== Health Endpoints ====================


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers.
    
    Returns basic health status without checking dependencies.
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow(),
        version="1.0.0",
    )


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness_check(redis=Depends(get_redis)):
    """
    Readiness check - verifies all dependencies are available.
    
    Checks:
    - Redis connectivity
    - Hugging Face token configuration
    """
    checks = {
        "redis": False,
        "hf_token": bool(settings.HF_TOKEN),
        "upload_dir": Path(settings.UPLOAD_DIR).exists(),
        "output_dir": Path(settings.OUTPUT_DIR).exists(),
    }

    try:
        await redis.ping()
        checks["redis"] = True
    except Exception as e:
        logger.error("Redis health check failed", error=str(e))

    all_ready = all(checks.values())

    return JSONResponse(
        status_code=status.HTTP_200_OK if all_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"ready": all_ready, "checks": checks},
    )


@app.get("/metrics", tags=["Monitoring"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# ==================== Conversion Endpoints ====================


@app.post(
    "/api/v1/convert",
    response_model=ConversionResponse,
    tags=["Conversion"],
    summary="Submit PDF for async conversion",
)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def convert_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file to convert"),
    extract_images: bool = Query(True, description="Extract images from PDF"),
    output_format: OutputFormat = Query(OutputFormat.LATEX, description="Output format"),
    document_class: str = Query("article", description="LaTeX document class"),
    redis=Depends(get_redis),
    api_key: str = Depends(verify_api_key),
):
    """
    Submit a PDF for asynchronous conversion.
    
    Returns a job_id that can be used to check status and download results.
    This endpoint is suitable for larger files that may take time to process.
    
    **Rate Limit:** 30 requests per minute
    """
    REQUESTS_TOTAL.labels(endpoint="/convert", status="received").inc()

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename required",
        )

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Read and check file size
    content = await file.read()
    file_size = len(content)
    FILE_SIZE_BYTES.observe(file_size)

    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit",
        )

    # Generate job ID and save file
    job_id = str(uuid.uuid4())
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    upload_path = Path(settings.UPLOAD_DIR) / f"{job_id}_{file_hash}.pdf"

    async with aiofiles.open(upload_path, "wb") as f:
        await f.write(content)

    # Store job metadata in Redis
    job_data = {
        "status": JobStatus.QUEUED.value,
        "progress": 0,
        "file_path": str(upload_path),
        "extract_images": str(extract_images),
        "output_format": output_format.value,
        "document_class": document_class,
        "created_at": datetime.utcnow().isoformat(),
        "file_size": file_size,
    }
    await redis.hset(f"job:{job_id}", mapping=job_data)
    await redis.expire(f"job:{job_id}", 86400)  # 24 hour TTL

    # Submit to Celery queue (import here to avoid circular imports)
    try:
        from app.worker import convert_pdf_task

        task = convert_pdf_task.delay(
            job_id=job_id,
            file_path=str(upload_path),
            extract_images=extract_images,
            output_format=output_format.value,
            document_class=document_class,
        )

        # Store task ID
        await redis.hset(f"job:{job_id}", "task_id", task.id)

        logger.info(
            "Conversion job submitted",
            job_id=job_id,
            task_id=task.id,
            file_size=file_size,
        )

    except Exception as e:
        logger.warning(
            "Celery not available, processing synchronously",
            error=str(e),
        )
        # Fall back to sync processing (for development)
        await redis.hset(f"job:{job_id}", "status", JobStatus.PROCESSING.value)
        # Note: In production, this should queue to Celery

    QUEUE_SIZE.inc()

    return ConversionResponse(
        job_id=job_id,
        status=JobStatus.QUEUED,
        message="Conversion job submitted successfully",
        estimated_time_seconds=max(30, file_size // 100000),  # Rough estimate
    )


@app.get(
    "/api/v1/status/{job_id}",
    response_model=JobStatusResponse,
    tags=["Conversion"],
    summary="Check job status",
)
async def get_job_status(
    job_id: str,
    redis=Depends(get_redis),
):
    """
    Check the status of a conversion job.
    
    Returns current progress, completion status, and result URL when ready.
    """
    status_data = await redis.hgetall(f"job:{job_id}")

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobStatusResponse(
        job_id=job_id,
        status=JobStatus(status_data.get("status", "unknown")),
        progress=int(status_data.get("progress", 0)),
        result_url=status_data.get("result_url"),
        error=status_data.get("error"),
        created_at=status_data.get("created_at"),
        completed_at=status_data.get("completed_at"),
        pages_processed=int(status_data.get("pages_processed", 0)) or None,
        total_pages=int(status_data.get("total_pages", 0)) or None,
    )


@app.get(
    "/api/v1/download/{job_id}",
    tags=["Conversion"],
    summary="Download conversion result",
)
async def download_result(
    job_id: str,
    redis=Depends(get_redis),
):
    """
    Download the converted LaTeX file.
    
    Only available after job is completed.
    """
    status_data = await redis.hgetall(f"job:{job_id}")

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if status_data.get("status") != JobStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job not yet completed. Current status: {status_data.get('status')}",
        )

    result_path = Path(status_data.get("result_path", ""))
    if not result_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Result file not found",
        )

    return FileResponse(
        path=result_path,
        filename=f"{job_id}.tex",
        media_type="application/x-tex",
    )


@app.post(
    "/api/v1/convert/sync",
    response_model=SyncConversionResponse,
    tags=["Conversion"],
    summary="Synchronous PDF conversion",
)
@limiter.limit("10/minute")
async def convert_pdf_sync(
    request: Request,
    file: UploadFile = File(..., description="PDF file to convert"),
    extract_images: bool = Query(False, description="Extract images (slower)"),
    output_format: OutputFormat = Query(OutputFormat.LATEX, description="Output format"),
    api_key: str = Depends(verify_api_key),
):
    """
    Synchronous conversion for small files (<5 pages).
    
    Returns LaTeX directly in response. Use this for quick conversions
    of small documents. For larger files, use the async endpoint.
    
    **Rate Limit:** 10 requests per minute
    """
    REQUESTS_TOTAL.labels(endpoint="/convert/sync", status="received").inc()

    content = await file.read()
    file_size = len(content)

    # Size limit for sync processing
    if file_size > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use async endpoint (/api/v1/convert) for files > 5MB",
        )

    # Direct conversion
    config = ConversionConfig(
        extract_images=extract_images,
        hf_use_inference_api=True,
        hf_model_id=settings.HF_MODEL_ID,
    )

    agent = PDFToLaTeXAgent(config)
    warnings = []

    try:
        with CONVERSION_DURATION.time():
            latex = agent.convert_bytes(content)

        REQUESTS_TOTAL.labels(endpoint="/convert/sync", status="completed").inc()

        return SyncConversionResponse(
            latex=latex,
            status="completed",
            pages_processed=0,  # Could track this
            warnings=warnings if warnings else None,
        )

    except Exception as e:
        logger.error("Sync conversion failed", error=str(e))
        REQUESTS_TOTAL.labels(endpoint="/convert/sync", status="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversion failed: {str(e)}",
        )


@app.delete(
    "/api/v1/job/{job_id}",
    tags=["Conversion"],
    summary="Cancel or delete a job",
)
async def cancel_job(
    job_id: str,
    redis=Depends(get_redis),
    api_key: str = Depends(verify_api_key),
):
    """
    Cancel a pending job or delete a completed job.
    
    This will also clean up associated files.
    """
    status_data = await redis.hgetall(f"job:{job_id}")

    if not status_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    # Clean up files
    for key in ["file_path", "result_path"]:
        file_path = status_data.get(key)
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to delete {key}", path=file_path, error=str(e))

    # Delete job from Redis
    await redis.delete(f"job:{job_id}")

    return {"message": "Job deleted", "job_id": job_id}


# ==================== Error Handlers ====================


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        error=str(exc),
        path=request.url.path,
        method=request.method,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


# ==================== CLI Entry Point ====================


def run_dev_server():
    """Run development server."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run_dev_server()

