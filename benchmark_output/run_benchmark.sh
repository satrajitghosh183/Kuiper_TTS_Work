#!/bin/bash
#
# PDF-to-LaTeX Benchmark Runner
# 
# Tests the converter with multiple papers and tracks performance metrics.
#
# Papers tested:
# 1. Friis - Introduction to Radio and Antennas (local)
# 2. LoRA - Low-Rank Adaptation of Large Language Models (arXiv)
# 3. Attention Is All You Need - Transformer paper (arXiv)
# 4. BERT - Pre-training of Transformers (arXiv)
# 5. QLoRA - Efficient Finetuning (arXiv)
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/benchmark_output"
MODEL="Qwen/Qwen2.5-VL-7B-Instruct"

# Load HF_TOKEN from .env if it exists
if [ -f "${PROJECT_ROOT}/.env" ]; then
    set -a
    source "${PROJECT_ROOT}/.env"
    set +a
fi

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}         PDF-to-LaTeX Benchmark Runner                       ${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Parse arguments
MAX_PAGES=""
NUM_PAPERS=""
DPI="200"
QUICK_TEST=false

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --max-pages) MAX_PAGES="--max-pages $2"; shift ;;
        --papers) NUM_PAPERS="--papers $2"; shift ;;
        --dpi) DPI="$2"; shift ;;
        --quick) QUICK_TEST=true ;;
        --model) MODEL="$2"; shift ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --max-pages N    Limit pages per paper (useful for testing)"
            echo "  --papers N       Limit number of papers to test"
            echo "  --dpi N          PDF rendering DPI (default: 200)"
            echo "  --model NAME     HuggingFace model ID"
            echo "  --quick          Quick test mode (2 papers, 3 pages each)"
            echo "  -h, --help       Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                      # Run full benchmark"
            echo "  $0 --quick              # Quick test (2 papers, 3 pages)"
            echo "  $0 --papers 3           # Test only first 3 papers"
            echo "  $0 --max-pages 5        # Process max 5 pages per paper"
            exit 0
            ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done

# Quick test mode
if [ "$QUICK_TEST" = true ]; then
    echo -e "${YELLOW}Running in QUICK TEST mode${NC}"
    MAX_PAGES="--max-pages 3"
    NUM_PAPERS="--papers 2"
fi

# Set up environment
export HF_TOKEN="$HF_TOKEN"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Check Python environment
echo -e "${BLUE}Checking environment...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 not found${NC}"
    exit 1
fi

# Check if dependencies are installed
echo -e "${BLUE}Checking dependencies...${NC}"
python3 -c "import fitz, PIL, structlog, rich, huggingface_hub" 2>/dev/null || {
    echo -e "${YELLOW}Installing missing dependencies...${NC}"
    pip install PyMuPDF Pillow structlog rich huggingface_hub
}

# Check if Friis paper exists
FRIIS_PAPER="${SCRIPT_DIR}/Friis Teaches an Introduction_to_radio_and_radio_antennas April 1971.pdf"
if [ -f "$FRIIS_PAPER" ]; then
    echo -e "${GREEN}✓ Friis paper found${NC}"
else
    echo -e "${YELLOW}Warning: Friis paper not found at expected location${NC}"
    echo -e "  Expected: $FRIIS_PAPER"
fi

# Print configuration
echo ""
echo -e "${BLUE}Configuration:${NC}"
echo "  Model: $MODEL"
echo "  Output: $OUTPUT_DIR"
echo "  DPI: $DPI"
if [ -n "$MAX_PAGES" ]; then
    echo "  Max pages: ${MAX_PAGES#--max-pages }"
fi
if [ -n "$NUM_PAPERS" ]; then
    echo "  Papers: ${NUM_PAPERS#--papers }"
fi
echo ""

# Run the benchmark
echo -e "${BLUE}Starting benchmark...${NC}"
echo ""

START_TIME=$(date +%s)

python3 "${SCRIPT_DIR}/benchmark_papers.py" \
    --output-dir "$OUTPUT_DIR" \
    --model "$MODEL" \
    --dpi "$DPI" \
    $MAX_PAGES \
    $NUM_PAPERS

EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"

if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}Benchmark completed successfully!${NC}"
else
    echo -e "${YELLOW}Benchmark completed with some failures${NC}"
fi

echo "Total wall time: ${DURATION}s"
echo ""
echo "Output files:"
ls -la "$OUTPUT_DIR"/*.tex 2>/dev/null || echo "  No .tex files generated"
echo ""
echo "Report: ${OUTPUT_DIR}/benchmark_report.json"

exit $EXIT_CODE
