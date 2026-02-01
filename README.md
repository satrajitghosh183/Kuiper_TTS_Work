# PDF-to-LaTeX Conversion System

[![CI](https://github.com/your-org/pdf-to-latex/actions/workflows/ci.yml/badge.svg)](https://github.com/your-org/pdf-to-latex/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

An **agentic AI system** for converting PDF documents to high-quality, compilable LaTeX source code using Vision Language Models (VLMs).

---

## Overview

The system takes a PDF file (or URL), renders each page as an image, sends those images to a Vision Language Model (VLM) for OCR/understanding, and assembles the model's output into a valid LaTeX document.

**Data Flow:**

```
PDF (file or URL)
    ↓
PyMuPDF: render pages → images
    ↓
VLM (Hugging Face / Ollama / Local): image + prompt → LaTeX per page
    ↓
LaTeXCleaner: clean and fix
    ↓
LaTeXDocumentGenerator: add preamble, packages
    ↓
Optional: extract figures, validate syntax/compilation
    ↓
.tex file
```

---

## Features

- **Multimodal Parsing**: Uses Vision Language Models via Hugging Face Inference API or Ollama (local)
- **Mathematical Content**: Accurate conversion of equations to LaTeX math mode
- **Table Recognition**: Converts tables to proper tabular/booktabs environments
- **Image Extraction**: Optional extraction and referencing of figures
- **LaTeX Validation**: Automatic syntax checking and compilation validation
- **CLI Interface**: Simple command-line usage

---

## Prerequisites

| Requirement | Version | How to Check | How to Install |
|-------------|---------|--------------|----------------|
| Python | 3.10+ | `python3 --version` | [python.org](https://python.org) |
| pip | Latest | `pip --version` | `python3 -m pip install --upgrade pip` |
| Hugging Face Token | - | - | [Get token here](https://huggingface.co/settings/tokens) |

**For local inference (no API):** Install [Ollama](https://ollama.ai/download) and pull a vision model.

---

## Installation

### Step 1: Clone or Navigate to the Project

```bash
cd PDF_to_Latex
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Set Environment Variables

**For Hugging Face (cloud inference):**

```bash
export HF_TOKEN="hf_your_token_here"
```

Or create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
# Edit .env and add your HF_TOKEN
```

**For Ollama (local, no API):** Install [Ollama](https://ollama.ai/download) and run `ollama pull llava:13b`.

### Step 5: Verify Installation

```bash
python -m app.cli info
```

---

## Quick Start

```bash
# Using Hugging Face API (requires HF_TOKEN)
python -m app.cli convert paper.pdf -o output.tex --no-images

# Using Ollama (local, no API needed)
python -m app.cli convert paper.pdf -o output.tex --ollama
```

---

## CLI Commands Reference

All commands are run via `python -m app.cli <command> [options]`.

### `convert` — Convert a Single PDF to LaTeX

Convert a PDF file (or URL) to LaTeX.

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | auto | Output `.tex` file path |
| `--images` / `--no-images` | | `--images` | Extract images from PDF |
| `--class` | `-c` | `article` | LaTeX document class |
| `--model` | `-m` | varies | Model ID (HuggingFace or Ollama) |
| `--local` | | `false` | Use local GPU (HuggingFace Transformers) |
| `--ollama` | | `false` | Use Ollama (fully local, no API) |
| `--ollama-host` | | `http://localhost:11434` | Ollama server URL |
| `--provider` | `-p` | auto | Provider: `huggingface`, `ollama`, `openai`, `google` |
| `--dpi` | | `200` | PDF rendering DPI |

**Examples:**

```bash
# Hugging Face Inference API (requires HF_TOKEN)
python -m app.cli convert paper.pdf -o paper.tex
python -m app.cli convert paper.pdf --model nanonets/Nanonets-OCR-s
python -m app.cli convert "https://arxiv.org/pdf/2106.09685.pdf" -o lora_paper.tex --no-images

# Ollama (completely local, no API needed)
python -m app.cli convert paper.pdf --ollama
python -m app.cli convert paper.pdf --ollama --model llava:13b
python -m app.cli convert paper.pdf --ollama --model bakllava

# Local HuggingFace Transformers (requires GPU)
python -m app.cli convert paper.pdf --local

# Custom DPI and document class
python -m app.cli convert paper.pdf -o output.tex --dpi 150 -c report
```

---

### `batch` — Convert Multiple PDFs

Convert all PDFs in a directory in parallel.

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `./output` | Output directory |
| `--pattern` | `-p` | `*.pdf` | File glob pattern |
| `--workers` | `-w` | `4` | Number of parallel workers |

**Examples:**

```bash
python -m app.cli batch ./pdfs/ -o ./output/
python -m app.cli batch ./papers/ -o ./latex_output/ -w 2
python -m app.cli batch ./documents/ -p "*.pdf" -o ./tex_output/
```

---

### `info` — Show Configuration

Display environment variables, API key status, settings, and recommended models.

```bash
python -m app.cli info
```

Shows: `HF_TOKEN`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, Ollama status, model IDs, paths, DPI, etc.

---

### `models` — List Available Models

List recommended Hugging Face and Ollama models. Optionally filter by provider.

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--provider` | `-p` | `all` | Filter: `huggingface`, `ollama`, `all` |

**Examples:**

```bash
python -m app.cli models
python -m app.cli models --provider ollama
python -m app.cli models --provider huggingface
```

---

### `pull` — Download Ollama Model

Pull an Ollama vision model for local inference.

**Examples:**

```bash
python -m app.cli pull llava:13b
python -m app.cli pull bakllava
python -m app.cli pull llava:7b
```

---

### `validate` — Compare PDF vs LaTeX Quality

Compare the original PDF and generated LaTeX to assess conversion quality. Reports word counts, character counts, structure (sections, equations, tables, figures), vocabulary overlap, and coverage percentages.

| Option | Short | Description |
|--------|-------|-------------|
| `--output` | `-o` | Save full report to JSON file |
| `--brief` | `-b` | Show brief summary only |

**Examples:**

```bash
python -m app.cli validate paper.pdf paper.tex
python -m app.cli validate paper.pdf paper.tex --brief
python -m app.cli validate paper.pdf paper.tex -o report.json
```

**Exit codes:** `0` = good coverage (≥70%), `1` = partial (50–70%), `2` = low (&lt;50%).

---

### `compare` — Page-by-Page Comparison

Show detailed page-by-page comparison between PDF and LaTeX (word coverage, character coverage, sections, math, status per page).

| Option | Short | Description |
|--------|-------|-------------|
| `--page` | `-p` | Compare specific page only |

**Examples:**

```bash
python -m app.cli compare paper.pdf paper.tex
python -m app.cli compare paper.pdf paper.tex --page 3
```

---

## Recommended Models

### Hugging Face (Cloud API — requires `HF_TOKEN`)

| Use Case | Model ID |
|----------|----------|
| General | `Qwen/Qwen2.5-VL-7B-Instruct` |
| Equations | `nanonets/Nanonets-OCR-s` |
| Tables | `microsoft/table-transformer-detection` |
| Formatted | `stepfun-ai/GOT-OCR2_0` |
| Fast | `reducto/RolmOCR` |

### Ollama (Local — no API needed)

| Use Case | Model Name |
|----------|------------|
| General | `llava:13b` (recommended) |
| Fast | `llava:7b` |
| Quality | `llava:34b` (needs 24GB+ VRAM) |
| Documents | `bakllava` |
| Llama 3 | `llava-llama3` |
| Efficient | `minicpm-v` |
| Lightweight | `moondream` |

---

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HF_TOKEN` | Hugging Face API token | - | Yes (for cloud) |
| `HF_MODEL_ID` | Model for OCR | `Qwen/Qwen2.5-VL-7B-Instruct` | No |
| `HF_USE_INFERENCE_API` | Use HF Inference API vs local | `true` | No |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` | No |
| `OLLAMA_MODEL` | Default Ollama model | `llava:13b` | No |
| `OPENAI_API_KEY` | OpenAI API key (fallback) | - | No |
| `GOOGLE_API_KEY` | Google API key (fallback) | - | No |
| `DPI` | PDF rendering resolution | `200` | No |
| `LOG_LEVEL` | Logging level | `INFO` | No |

---

## Project Structure & Code Explanation

```
PDF_to_Latex/
├── app/
│   ├── cli.py              # Command-line interface (main entry point)
│   ├── config.py           # Configuration and settings
│   ├── exceptions.py       # Custom error types
│   ├── models.py           # Data models (PageContent, etc.)
│   ├── converter/          # Core conversion logic
│   │   ├── agent.py        # Main conversion agent (orchestrator)
│   │   ├── extractors.py   # Equation/table extraction helpers
│   │   ├── latex_utils.py  # LaTeX cleaning, validation, document generation
│   │   └── validator.py    # Quality validation (PDF vs LaTeX comparison)
│   └── ocr/                # Vision/OCR clients
│       ├── base.py         # Base OCR interface
│       ├── hf_client.py    # Hugging Face Inference API client
│       ├── local_client.py# Local GPU inference (HuggingFace Transformers)
│       ├── ollama_client.py# Ollama (fully local, no API)
│       └── prompts.py      # Prompts sent to the VLM
├── tests/                  # Unit tests
├── requirements.txt        # Python dependencies
└── .env.example            # Environment variable template
```

### What Each Component Does

| File | Purpose |
|------|---------|
| **cli.py** | Main entry point. Commands: `convert`, `batch`, `info`, `models`, `pull`, `validate`, `compare`. |
| **config.py** | `ConversionConfig` (DPI, document class, model, etc.), `Settings` (env vars), `RECOMMENDED_MODELS`, `OLLAMA_MODELS`. |
| **agent.py** | Loads PDF, renders pages, sends to VLM, combines output, generates LaTeX, optionally extracts images. `BatchConverter` runs multiple PDFs in parallel. |
| **latex_utils.py** | `LaTeXCleaner` (fixes braces, environments), `LaTeXDocumentGenerator` (preamble + body), `LaTeXValidator` (syntax/compilation). |
| **extractors.py** | Helpers for extracting equations and tables from model output. |
| **validator.py** | Compares PDF vs LaTeX: word/char counts, sections, equations, tables, figures, vocabulary overlap, per-page coverage. |
| **ocr/base.py** | Abstract base class for OCR clients. |
| **ocr/hf_client.py** | Hugging Face Inference API (cloud). Requires `HF_TOKEN`. |
| **ocr/local_client.py** | Hugging Face Transformers locally (needs GPU). |
| **ocr/ollama_client.py** | Ollama for fully local inference (no API key). |
| **ocr/prompts.py** | System and page prompts sent to the VLM. |
| **models.py** | Pydantic models: `PageContent`, `DocumentStructure`, `ExtractionResult`, etc. |
| **exceptions.py** | `ConversionError`, `PDFParseError`, `OCRError`, `FileError`, `ImageExtractionError`. |

---

## Dependencies (High Level)

- **PyMuPDF (fitz)**: PDF loading and page rendering
- **Pillow**: Image handling
- **requests**: HTTP (e.g., downloading PDFs from URLs)
- **Hugging Face / Ollama**: Vision models for OCR
- **typer + rich**: CLI and pretty output
- **pydantic**: Configuration and data validation

---

## Troubleshooting

### "HF_TOKEN not set" Error

```bash
export HF_TOKEN="hf_your_token_here"
```

Or use `--ollama` for local inference without an API.

### "ModuleNotFoundError"

```bash
source venv/bin/activate
pip install -r requirements.txt
```

### Rate Limit Errors (Hugging Face)

- Wait and retry
- Use `--ollama` for local inference
- Try a different model

### Slow Processing

```bash
# Use faster model
python -m app.cli convert paper.pdf -o output.tex --model reducto/RolmOCR

# Disable image extraction
python -m app.cli convert paper.pdf -o output.tex --no-images

# Lower DPI
python -m app.cli convert paper.pdf -o output.tex --dpi 150
```

### Ollama Not Running

Install from [ollama.ai/download](https://ollama.ai/download), then:

```bash
ollama serve
ollama pull llava:13b
```

---

## Running Tests

```bash
pip install pytest pytest-asyncio pytest-cov
pytest tests/ -v
```

---

## License

MIT License
