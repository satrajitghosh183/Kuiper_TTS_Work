"""
Celery worker for asynchronous PDF-to-LaTeX conversion.

This module provides background task processing using Celery and Redis.
It handles long-running conversion jobs with progress tracking and retry logic.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import redis as sync_redis
import structlog
from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun

from app.config import ConversionConfig, settings

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# Create Celery app
celery_app = Celery(
    "pdf_latex_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.TASK_TIMEOUT,
    task_soft_time_limit=settings.TASK_TIMEOUT - 60,
    worker_prefetch_multiplier=1,  # One task at a time for GPU workers
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_concurrency=settings.MAX_WORKERS,
    result_expires=86400,  # 24 hours
)

# Redis client for job status updates
redis_client = sync_redis.from_url(settings.REDIS_URL, decode_responses=True)


def _update_job_status(
    job_id: str,
    status: str,
    **kwargs,
) -> None:
    """
    Update job status in Redis.

    Args:
        job_id: Unique job identifier
        status: New status value
        **kwargs: Additional fields to update
    """
    data = {
        "status": status,
        "updated_at": datetime.utcnow().isoformat(),
        **{k: str(v) for k, v in kwargs.items()},
    }

    redis_client.hset(f"job:{job_id}", mapping=data)
    redis_client.expire(f"job:{job_id}", 86400)  # 24 hour TTL


# ==================== Celery Signals ====================


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, **kwargs):
    """Log when task starts."""
    if args and len(args) > 0:
        job_id = kwargs.get("kwargs", {}).get("job_id")
        if job_id:
            logger.info("Task started", task_id=task_id, job_id=job_id)


@task_postrun.connect
def task_postrun_handler(
    sender=None, task_id=None, task=None, args=None, retval=None, state=None, **kwargs
):
    """Log when task completes."""
    logger.info("Task completed", task_id=task_id, state=state)


@task_failure.connect
def task_failure_handler(
    sender=None, task_id=None, exception=None, args=None, traceback=None, **kwargs
):
    """Handle task failure."""
    job_id = kwargs.get("kwargs", {}).get("job_id")
    if job_id:
        _update_job_status(
            job_id,
            "failed",
            error=str(exception),
            completed_at=datetime.utcnow().isoformat(),
        )
    logger.error("Task failed", task_id=task_id, error=str(exception))


# ==================== Celery Tasks ====================


@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
)
def convert_pdf_task(
    self,
    job_id: str,
    file_path: str,
    extract_images: bool = True,
    output_format: str = "latex",
    document_class: str = "article",
) -> dict:
    """
    Celery task for PDF conversion.

    Supports retries with exponential backoff and progress tracking.

    Args:
        job_id: Unique job identifier
        file_path: Path to uploaded PDF file
        extract_images: Whether to extract images
        output_format: Output format (latex, markdown, plain)
        document_class: LaTeX document class

    Returns:
        Dictionary with job results
    """
    logger.info(
        "Starting PDF conversion task",
        job_id=job_id,
        file_path=file_path,
        retry=self.request.retries,
    )

    try:
        # Update status to processing
        _update_job_status(job_id, "processing", progress=10)

        # Import here to avoid circular imports
        from app.converter.agent import PDFToLaTeXAgent

        # Initialize converter
        config = ConversionConfig(
            extract_images=extract_images,
            document_class=document_class,
            primary_provider="huggingface",
            hf_use_inference_api=True,
            hf_model_id=settings.HF_MODEL_ID,
            hf_api_token=settings.HF_TOKEN,
        )

        agent = PDFToLaTeXAgent(config)

        # Progress callback
        def on_progress(page: int, total: int):
            progress = 10 + int((page / total) * 80)
            _update_job_status(
                job_id,
                "processing",
                progress=progress,
                pages_processed=page,
                total_pages=total,
            )

        agent.on_progress = on_progress

        # Determine output path
        output_dir = Path(settings.OUTPUT_DIR)
        output_path = output_dir / f"{job_id}.tex"

        # Convert PDF
        latex = agent.convert(file_path, str(output_path))

        # Mark complete
        _update_job_status(
            job_id,
            "completed",
            progress=100,
            result_path=str(output_path),
            result_url=f"/api/v1/download/{job_id}",
            completed_at=datetime.utcnow().isoformat(),
            latex_length=len(latex),
        )

        logger.info(
            "Conversion completed successfully",
            job_id=job_id,
            output_path=str(output_path),
            latex_length=len(latex),
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "output_path": str(output_path),
        }

    except Exception as e:
        logger.error(
            "Conversion failed",
            job_id=job_id,
            error=str(e),
            retry=self.request.retries,
        )

        # Update status
        _update_job_status(
            job_id,
            "failed",
            error=str(e),
            completed_at=datetime.utcnow().isoformat(),
        )

        # Re-raise for Celery retry logic
        raise


@celery_app.task(bind=True)
def cleanup_old_jobs(self, max_age_hours: int = 24) -> dict:
    """
    Periodic task to clean up old job files.

    Args:
        max_age_hours: Maximum age of files to keep

    Returns:
        Cleanup statistics
    """
    import time

    logger.info("Starting job cleanup", max_age_hours=max_age_hours)

    deleted_uploads = 0
    deleted_outputs = 0
    max_age_seconds = max_age_hours * 3600
    now = time.time()

    # Clean upload directory
    upload_dir = Path(settings.UPLOAD_DIR)
    if upload_dir.exists():
        for file in upload_dir.glob("*.pdf"):
            if now - file.stat().st_mtime > max_age_seconds:
                try:
                    file.unlink()
                    deleted_uploads += 1
                except Exception as e:
                    logger.warning("Failed to delete upload", path=str(file), error=str(e))

    # Clean output directory
    output_dir = Path(settings.OUTPUT_DIR)
    if output_dir.exists():
        for file in output_dir.glob("*.tex"):
            if now - file.stat().st_mtime > max_age_seconds:
                try:
                    file.unlink()
                    deleted_outputs += 1
                except Exception as e:
                    logger.warning("Failed to delete output", path=str(file), error=str(e))

    logger.info(
        "Job cleanup completed",
        deleted_uploads=deleted_uploads,
        deleted_outputs=deleted_outputs,
    )

    return {
        "deleted_uploads": deleted_uploads,
        "deleted_outputs": deleted_outputs,
    }


# ==================== Celery Beat Schedule ====================


celery_app.conf.beat_schedule = {
    "cleanup-old-jobs-daily": {
        "task": "app.worker.cleanup_old_jobs",
        "schedule": 86400.0,  # Every 24 hours
        "args": (24,),
    },
}

