# PDF-to-LaTeX Conversion System

[![CI](https://github.com/your-org/pdf-to-latex/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/pdf-to-latex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

An **agentic AI system** for converting PDF documents to high-quality, compilable LaTeX source code using Vision Language Models (VLMs) from Hugging Face.

---

## 📋 Table of Contents

- [Features](#-features)
- [Prerequisites](#-prerequisites)
- [Installation](#-installation)
- [Quick Start](#-quick-start)
- [Usage Examples](#-usage-examples)
- [Configuration](#-configuration)
- [API Server](#-api-server)
- [Docker Deployment](#-docker-deployment)
- [Kubernetes Deployment](#-kubernetes-deployment)
- [Troubleshooting](#-troubleshooting)
- [Project Structure](#-project-structure)

---

## ✨ Features

- **🤖 Multimodal Parsing**: Uses Vision Language Models via Hugging Face Inference API
- **📐 Mathematical Content**: Accurate conversion of equations to LaTeX math mode
- **📊 Table Recognition**: Converts tables to proper tabular/booktabs environments
- **🖼️ Image Extraction**: Toggleable feature to extract and reference figures
- **✅ LaTeX Validation**: Automatic syntax checking and compilation validation
- **🚀 Production Ready**: FastAPI server, Celery workers, Docker, Kubernetes

---

## 📦 Prerequisites

Before you begin, ensure you have:

| Requirement | Version | How to Check | How to Install |
|-------------|---------|--------------|----------------|
| Python | 3.10+ | `python3 --version` | [python.org](https://python.org) |
| pip | Latest | `pip --version` | `python3 -m pip install --upgrade pip` |
| Git | Any | `git --version` | [git-scm.com](https://git-scm.com) |
| Hugging Face Token | - | - | [Get token here](https://huggingface.co/settings/tokens) |

**Optional (for production):**
| Requirement | Purpose |
|-------------|---------|
| Docker | Containerized deployment |
| Redis | Async job processing |
| LaTeX (texlive) | PDF compilation validation |

---

## 🛠️ Installation

### Step 1: Clone or Navigate to the Project

```bash
cd /Users/satrajitghosh/Projects/Machine_Learning_Projects/PDF_to_Latex
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (macOS/Linux)
source venv/bin/activate

# Activate it (Windows)
# venv\Scripts\activate
```

You should see `(venv)` in your terminal prompt.

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4: Get Hugging Face API Token

1. Go to: https://huggingface.co/settings/tokens
2. Click **"New token"**
3. Name it (e.g., "pdf-to-latex")
4. Select **"Read"** access
5. Click **"Generate"**
6. Copy the token (starts with `hf_...`)

### Step 5: Set Environment Variable

```bash
# Set for current session
export HF_TOKEN="hf_your_actual_token_here"

# Or add to your shell profile for persistence
echo 'export HF_TOKEN="hf_your_actual_token_here"' >> ~/.zshrc
source ~/.zshrc
```

### Step 6: Verify Installation

```bash
python -m app.cli info
```

You should see a table showing your configuration and that HF_TOKEN is set.

---

## 🚀 Quick Start

### Convert Your First PDF

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Set your token (if not already set)
export HF_TOKEN="hf_your_token_here"

# Convert a paper from arXiv
python -m app.cli convert "https://arxiv.org/pdf/2106.09685.pdf" -o lora_paper.tex --no-images
```

### Check the Output

```bash
# View the generated LaTeX
cat lora_paper.tex

# Or open in your default editor (macOS)
open lora_paper.tex
```

---

## 📚 Usage Examples

### Command Line Interface (CLI)

#### Basic Conversion

```bash
# Convert from URL
python -m app.cli convert "https://arxiv.org/pdf/1706.03762.pdf" -o transformer.tex

# Convert local file
python -m app.cli convert /path/to/your/paper.pdf -o output.tex

# Convert without extracting images (faster)
python -m app.cli convert paper.pdf -o output.tex --no-images
```

#### Famous Papers to Test With

```bash
# Attention Is All You Need (Transformer)
python -m app.cli convert "https://arxiv.org/pdf/1706.03762.pdf" -o transformer.tex --no-images

# BERT
python -m app.cli convert "https://arxiv.org/pdf/1810.04805.pdf" -o bert.tex --no-images

# ResNet
python -m app.cli convert "https://arxiv.org/pdf/1512.03385.pdf" -o resnet.tex --no-images

# LoRA (shorter, good for testing)
python -m app.cli convert "https://arxiv.org/pdf/2106.09685.pdf" -o lora.tex --no-images

# Diffusion Models
python -m app.cli convert "https://arxiv.org/pdf/2006.11239.pdf" -o diffusion.tex --no-images
```

#### Advanced Options

```bash
# Use a different model (better for equations)
python -m app.cli convert paper.pdf -o output.tex --model nanonets/Nanonets-OCR-s

# Specify document class
python -m app.cli convert paper.pdf -o output.tex --class report

# Higher DPI for better quality (slower)
python -m app.cli convert paper.pdf -o output.tex --dpi 300

# Extract images too
python -m app.cli convert paper.pdf -o output.tex --images
```

#### Batch Conversion

```bash
# Convert all PDFs in a directory
python -m app.cli batch ./papers/ -o ./latex_output/ -w 4
```

#### Show Configuration

```bash
python -m app.cli info
```

### Python API

#### Basic Usage

```python
import os
os.environ["HF_TOKEN"] = "hf_your_token_here"

from app.config import ConversionConfig
from app.converter import PDFToLaTeXAgent

# Create agent with default config
config = ConversionConfig()
agent = PDFToLaTeXAgent(config)

# Convert PDF
latex = agent.convert("paper.pdf", "output.tex")
print(f"Generated {len(latex)} characters")
```

#### Custom Configuration

```python
from app.config import ConversionConfig
from app.converter import PDFToLaTeXAgent

config = ConversionConfig(
    # Disable image extraction for speed
    extract_images=False,
    
    # Use equation-optimized model
    hf_model_id="nanonets/Nanonets-OCR-s",
    
    # Higher resolution
    dpi=300,
    
    # Document settings
    document_class="article",
    use_packages=["amsmath", "amssymb", "graphicx", "hyperref"],
)

agent = PDFToLaTeXAgent(config)
latex = agent.convert("math_paper.pdf", "output.tex")
```

#### Convert from URL

```python
from app.converter import PDFToLaTeXAgent

agent = PDFToLaTeXAgent()
latex = agent.convert(
    "https://arxiv.org/pdf/1706.03762.pdf",
    "transformer.tex"
)
```

#### Convert from Bytes

```python
from app.converter import PDFToLaTeXAgent

# Read PDF file
with open("paper.pdf", "rb") as f:
    pdf_bytes = f.read()

agent = PDFToLaTeXAgent()
latex = agent.convert_bytes(pdf_bytes, "output.tex")
```

---

## ⚙️ Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HF_TOKEN` | Hugging Face API token | - | **Yes** |
| `HF_MODEL_ID` | Model to use for OCR | `Qwen/Qwen2.5-VL-7B-Instruct` | No |
| `REDIS_URL` | Redis connection (for API) | `redis://localhost:6379` | No |
| `API_KEY` | API authentication key | - | No |
| `MAX_FILE_SIZE_MB` | Max upload size | `50` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |
| `DPI` | PDF rendering resolution | `200` | No |

### Recommended Models

| Use Case | Model ID | Command |
|----------|----------|---------|
| **General** (default) | `Qwen/Qwen2.5-VL-7B-Instruct` | `--model Qwen/Qwen2.5-VL-7B-Instruct` |
| **Math/Equations** | `nanonets/Nanonets-OCR-s` | `--model nanonets/Nanonets-OCR-s` |
| **Fast Processing** | `reducto/RolmOCR` | `--model reducto/RolmOCR` |
| **Formatted Text** | `stepfun-ai/GOT-OCR2_0` | `--model stepfun-ai/GOT-OCR2_0` |

### Create .env File (Optional)

```bash
cp .env.example .env
```

Edit `.env`:
```env
HF_TOKEN=hf_your_token_here
HF_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct
LOG_LEVEL=INFO
DPI=200
```

---

## 🌐 API Server

### Start Development Server

```bash
# Activate virtual environment
source venv/bin/activate

# Set token
export HF_TOKEN="hf_your_token"

# Start server
python -m app.cli serve --port 8000 --reload
```

Server will be available at: http://localhost:8000

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/metrics` | GET | Prometheus metrics |
| `/api/v1/convert` | POST | Async conversion (returns job ID) |
| `/api/v1/convert/sync` | POST | Sync conversion (returns LaTeX) |
| `/api/v1/status/{job_id}` | GET | Check job status |
| `/api/v1/download/{job_id}` | GET | Download result |

### Using the API with curl

#### Synchronous Conversion (Small Files)

```bash
curl -X POST "http://localhost:8000/api/v1/convert/sync" \
  -H "X-API-Key: your_api_key" \
  -F "file=@paper.pdf" \
  -o result.json
```

#### Async Conversion (Large Files)

```bash
# Submit job
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "X-API-Key: your_api_key" \
  -F "file=@paper.pdf"

# Response: {"job_id": "abc123", "status": "queued", ...}

# Check status
curl "http://localhost:8000/api/v1/status/abc123"

# Download when complete
curl "http://localhost:8000/api/v1/download/abc123" -o result.tex
```

### Using the API with Python

```python
import requests

# Sync conversion
with open("paper.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/convert/sync",
        files={"file": f},
        headers={"X-API-Key": "your_api_key"}
    )

result = response.json()
print(result["latex"])
```

---

## 🐳 Docker Deployment

### Quick Start with Docker Compose

```bash
# Set your token
export HF_TOKEN="hf_your_token_here"

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f api

# Stop services
docker-compose down
```

### Services Started

| Service | Port | Description |
|---------|------|-------------|
| api | 8000 | FastAPI server |
| worker | - | Celery worker |
| redis | 6379 | Message queue |
| prometheus | 9090 | Metrics |
| grafana | 3000 | Dashboards |
| flower | 5555 | Celery monitor |

### Access Points

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Flower**: http://localhost:5555 (admin/admin)
- **Prometheus**: http://localhost:9090

### Build Images Manually

```bash
# Build API image
docker build -t pdf-to-latex-api .

# Build worker image
docker build -f Dockerfile.worker -t pdf-to-latex-worker .

# Run API container
docker run -d \
  -p 8000:8000 \
  -e HF_TOKEN="hf_your_token" \
  -e REDIS_URL="redis://host.docker.internal:6379" \
  pdf-to-latex-api
```

### Docker Compose with Custom Config

```bash
# Create .env file
cat > .env << EOF
HF_TOKEN=hf_your_token_here
HF_MODEL_ID=Qwen/Qwen2.5-VL-7B-Instruct
MAX_FILE_SIZE_MB=100
GRAFANA_PASSWORD=secure_password
FLOWER_USER=admin
FLOWER_PASSWORD=secure_password
EOF

# Start with custom config
docker-compose up -d
```

---

## ☸️ Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (minikube, EKS, GKE, AKS)
- kubectl configured
- Container registry access

### Step 1: Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### Step 2: Create Secrets

Edit `k8s/secrets.yaml` with your actual tokens:

```yaml
stringData:
  hf-token: "hf_your_actual_token"
  api-key: "your_api_key"
  redis-password: "your_redis_password"
```

```bash
kubectl apply -f k8s/secrets.yaml
```

### Step 3: Create ConfigMap

```bash
kubectl apply -f k8s/configmap.yaml
```

### Step 4: Deploy Redis

```bash
kubectl apply -f k8s/redis.yaml
```

### Step 5: Deploy API and Workers

```bash
# Deploy API
kubectl apply -f k8s/api-deployment.yaml

# Deploy workers
kubectl apply -f k8s/worker-deployment.yaml

# Enable autoscaling
kubectl apply -f k8s/hpa.yaml

# Create ingress (optional)
kubectl apply -f k8s/ingress.yaml
```

### Step 6: Verify Deployment

```bash
# Check pods
kubectl -n pdf-to-latex get pods

# Check services
kubectl -n pdf-to-latex get services

# Check logs
kubectl -n pdf-to-latex logs -f deployment/pdf-latex-api

# Port forward for testing
kubectl -n pdf-to-latex port-forward svc/pdf-latex-service 8000:80
```

### Full Deployment Script

```bash
#!/bin/bash
# deploy.sh

# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/redis.yaml
kubectl apply -f k8s/api-deployment.yaml
kubectl apply -f k8s/worker-deployment.yaml
kubectl apply -f k8s/hpa.yaml

# Wait for rollout
kubectl -n pdf-to-latex rollout status deployment/pdf-latex-api --timeout=300s
kubectl -n pdf-to-latex rollout status deployment/pdf-latex-worker --timeout=300s

echo "Deployment complete!"
kubectl -n pdf-to-latex get pods
```

### Cleanup

```bash
kubectl delete namespace pdf-to-latex
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. "HF_TOKEN not set" Error

```bash
# Check if token is set
echo $HF_TOKEN

# Set it
export HF_TOKEN="hf_your_token_here"
```

#### 2. "ModuleNotFoundError"

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### 3. "Connection refused" (Redis)

```bash
# Start Redis locally
brew install redis  # macOS
brew services start redis

# Or use Docker
docker run -d -p 6379:6379 redis:7-alpine
```

#### 4. Rate Limit Errors

The Hugging Face Inference API has rate limits. Solutions:
- Wait and retry
- Use a different model
- Use local inference (requires GPU)

#### 5. Slow Processing

```bash
# Use faster model
python -m app.cli convert paper.pdf -o output.tex --model reducto/RolmOCR

# Disable image extraction
python -m app.cli convert paper.pdf -o output.tex --no-images

# Lower DPI
python -m app.cli convert paper.pdf -o output.tex --dpi 150
```

#### 6. LaTeX Compilation Errors

The generated LaTeX may need manual fixes. Common issues:
- Missing packages: Add to preamble
- Unbalanced braces: Check equations
- Special characters: Escape with `\`

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
python -m app.cli convert paper.pdf -o output.tex
```

### Check System Status

```bash
# Show configuration
python -m app.cli info

# Test API health
curl http://localhost:8000/health

# Test API readiness
curl http://localhost:8000/ready
```

---

## 📁 Project Structure

```
PDF_to_Latex/
├── app/                          # Main application
│   ├── __init__.py
│   ├── cli.py                    # Command-line interface
│   ├── config.py                 # Configuration management
│   ├── dependencies.py           # FastAPI dependencies
│   ├── exceptions.py             # Custom exceptions
│   ├── main.py                   # FastAPI server
│   ├── models.py                 # Pydantic models
│   ├── worker.py                 # Celery worker
│   ├── converter/
│   │   ├── __init__.py
│   │   ├── agent.py              # Main conversion agent
│   │   ├── extractors.py         # Equation/table extractors
│   │   └── latex_utils.py        # LaTeX utilities
│   └── ocr/
│       ├── __init__.py
│       ├── base.py               # Base OCR client
│       ├── hf_client.py          # HuggingFace API client
│       ├── local_client.py       # Local GPU inference
│       └── prompts.py            # OCR prompts
├── tests/                        # Test suite
│   ├── conftest.py
│   ├── test_api.py
│   ├── test_config.py
│   ├── test_extractors.py
│   └── test_latex_utils.py
├── k8s/                          # Kubernetes manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── redis.yaml
│   ├── api-deployment.yaml
│   ├── worker-deployment.yaml
│   ├── hpa.yaml
│   └── ingress.yaml
├── .github/workflows/            # CI/CD
│   ├── ci.yml
│   └── deploy.yml
├── Dockerfile                    # API container
├── Dockerfile.worker             # Worker container
├── docker-compose.yml            # Full stack
├── prometheus.yml                # Prometheus config
├── pyproject.toml                # Python project config
├── requirements.txt              # Dependencies
├── .env.example                  # Environment template
└── README.md                     # This file
```

---

## 🧪 Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html

# Run specific test file
pytest tests/test_latex_utils.py -v
```

---

## 📄 License

This project is licensed under the MIT License.

---

## 🆘 Getting Help

1. Check the [Troubleshooting](#-troubleshooting) section
2. Run `python -m app.cli info` to verify configuration
3. Check logs with `LOG_LEVEL=DEBUG`
4. Open an issue on GitHub

---

## 🎯 Quick Reference

```bash
# Setup
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export HF_TOKEN="hf_xxx"

# Convert PDF
python -m app.cli convert paper.pdf -o output.tex --no-images

# Start API
python -m app.cli serve --port 8000

# Docker
docker-compose up -d

# Kubernetes
kubectl apply -f k8s/
```

---

**⭐ Star this repo if you find it useful!**
