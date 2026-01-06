# ===========================================
# PDF-to-LaTeX Conversion System
# Multi-stage Docker build for production
# ===========================================

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /build/wheels -r requirements.txt


# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Labels
LABEL maintainer="PDF-to-LaTeX Team"
LABEL version="1.0.0"
LABEL description="Agentic PDF-to-LaTeX Conversion System"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # LaTeX for validation
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-science \
    # PDF processing
    poppler-utils \
    # Image processing
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    # Health check
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy wheels from builder and install
COPY --from=builder /build/wheels /wheels
RUN pip install --no-cache-dir /wheels/* \
    && rm -rf /wheels

# Copy application code
COPY app/ /app/app/
COPY pyproject.toml /app/

# Create non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser \
    && mkdir -p /app/uploads /app/outputs /app/figures \
    && chown -R appuser:appuser /app

USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

