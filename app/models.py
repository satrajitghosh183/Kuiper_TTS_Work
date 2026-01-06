"""
Pydantic models for API request/response validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Output format options."""

    LATEX = "latex"
    MARKDOWN = "markdown"
    PLAIN = "plain"


# ==================== Request Models ====================


class ConversionRequest(BaseModel):
    """Request model for PDF conversion."""

    extract_images: bool = Field(
        default=True, description="Whether to extract images from PDF"
    )
    output_format: OutputFormat = Field(
        default=OutputFormat.LATEX, description="Output format"
    )
    document_class: str = Field(
        default="article", description="LaTeX document class"
    )
    custom_packages: Optional[List[str]] = Field(
        default=None, description="Additional LaTeX packages to include"
    )
    generate_captions: bool = Field(
        default=True, description="Generate captions for figures"
    )


class SyncConversionRequest(BaseModel):
    """Request model for synchronous conversion."""

    extract_images: bool = Field(default=False, description="Extract images")
    output_format: OutputFormat = Field(
        default=OutputFormat.LATEX, description="Output format"
    )


# ==================== Response Models ====================


class ConversionResponse(BaseModel):
    """Response model for async conversion job submission."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Status message")
    estimated_time_seconds: Optional[int] = Field(
        default=None, description="Estimated processing time"
    )


class JobStatusResponse(BaseModel):
    """Response model for job status check."""

    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    progress: int = Field(
        default=0, ge=0, le=100, description="Progress percentage"
    )
    result_url: Optional[str] = Field(
        default=None, description="URL to download result"
    )
    error: Optional[str] = Field(default=None, description="Error message if failed")
    created_at: Optional[datetime] = Field(
        default=None, description="Job creation timestamp"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Job completion timestamp"
    )
    pages_processed: Optional[int] = Field(
        default=None, description="Number of pages processed"
    )
    total_pages: Optional[int] = Field(
        default=None, description="Total number of pages"
    )


class SyncConversionResponse(BaseModel):
    """Response model for synchronous conversion."""

    latex: str = Field(..., description="Generated LaTeX content")
    status: str = Field(default="completed", description="Conversion status")
    pages_processed: int = Field(default=0, description="Number of pages processed")
    warnings: Optional[List[str]] = Field(
        default=None, description="Any warnings during conversion"
    )


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")


class ReadinessResponse(BaseModel):
    """Readiness check response."""

    ready: bool = Field(..., description="Whether service is ready")
    checks: dict = Field(..., description="Individual check results")


# ==================== Internal Models ====================


class PageContent(BaseModel):
    """Represents extracted content from a single page."""

    page_number: int = Field(..., description="Page number (1-indexed)")
    latex_content: str = Field(..., description="LaTeX content for this page")
    images: List[str] = Field(
        default_factory=list, description="Paths to extracted images"
    )
    equations: List[str] = Field(
        default_factory=list, description="Extracted equations"
    )
    tables: List[str] = Field(default_factory=list, description="Extracted tables")
    warnings: List[str] = Field(
        default_factory=list, description="Processing warnings"
    )


class DocumentStructure(BaseModel):
    """Represents the overall document structure."""

    title: Optional[str] = Field(default=None, description="Document title")
    authors: Optional[List[str]] = Field(default=None, description="Document authors")
    abstract: Optional[str] = Field(default=None, description="Document abstract")
    sections: List[str] = Field(
        default_factory=list, description="Section titles detected"
    )
    total_pages: int = Field(default=0, description="Total page count")
    has_bibliography: bool = Field(
        default=False, description="Whether document has bibliography"
    )
    document_type: str = Field(
        default="article", description="Detected document type"
    )


class ExtractionResult(BaseModel):
    """Result from specialized extraction agents."""

    content: str = Field(..., description="Extracted content")
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score"
    )
    source_page: int = Field(..., description="Source page number")
    bounding_box: Optional[List[float]] = Field(
        default=None, description="Bounding box coordinates [x1, y1, x2, y2]"
    )

