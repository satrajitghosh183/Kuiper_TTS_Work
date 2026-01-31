#!/usr/bin/env python3
"""
Benchmark script for PDF-to-LaTeX conversion.

Tests the converter with multiple papers and tracks:
- Time per page
- Characters per page
- Total conversion time
- Overall statistics

Papers tested:
1. Friis - "Friis Teaches an Introduction to Radio and Radio Antennas" (local file)
2. LoRA - Low-Rank Adaptation of Large Language Models (arXiv:2106.09685)
3. Attention Is All You Need - Transformer paper (arXiv:1706.03762)
4. BERT paper (arXiv:1810.04805)
5. GPT-2 paper (Language Models are Unsupervised Multitask Learners)
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import statistics

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# Load .env from project root (HF_TOKEN, etc.)
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

import structlog
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from app.config import ConversionConfig
from app.converter.agent import PDFToLaTeXAgent

logger = structlog.get_logger()
console = Console()


# Papers to benchmark
BENCHMARK_PAPERS = [
    {
        "name": "Friis - Introduction to Radio and Antennas",
        "path": "/Users/satrajitghosh/Projects/Machine_Learning_Projects/PDF_to_Latex/Friis Teaches an Introduction_to_radio_and_radio_antennas April 1971.pdf",
        "type": "local",
        "description": "Classic paper on radio fundamentals by Harald T. Friis (1971)",
    },
    {
        "name": "LoRA - Low-Rank Adaptation",
        "path": "https://arxiv.org/pdf/2106.09685.pdf",
        "type": "arxiv",
        "description": "LoRA: Low-Rank Adaptation of Large Language Models (2021)",
    },
    {
        "name": "Attention Is All You Need",
        "path": "https://arxiv.org/pdf/1706.03762.pdf",
        "type": "arxiv",
        "description": "The original Transformer paper by Vaswani et al. (2017)",
    },
    {
        "name": "BERT",
        "path": "https://arxiv.org/pdf/1810.04805.pdf",
        "type": "arxiv",
        "description": "BERT: Pre-training of Deep Bidirectional Transformers (2018)",
    },
    {
        "name": "QLoRA - Efficient Finetuning",
        "path": "https://arxiv.org/pdf/2305.14314.pdf",
        "type": "arxiv",
        "description": "QLoRA: Efficient Finetuning of Quantized LLMs (2023)",
    },
]


@dataclass
class PageStats:
    """Statistics for a single page."""
    page_number: int
    processing_time_seconds: float
    character_count: int
    word_count: int
    has_equations: bool = False
    has_tables: bool = False
    has_figures: bool = False


@dataclass
class PaperBenchmark:
    """Benchmark results for a single paper."""
    name: str
    path: str
    paper_type: str
    description: str
    
    # Timing
    total_time_seconds: float = 0.0
    download_time_seconds: float = 0.0
    
    # Page statistics
    total_pages: int = 0
    page_stats: List[PageStats] = field(default_factory=list)
    
    # Content statistics
    total_characters: int = 0
    total_words: int = 0
    
    # Output
    output_path: str = ""
    latex_size_bytes: int = 0
    
    # Status
    success: bool = False
    error_message: str = ""
    
    @property
    def avg_time_per_page(self) -> float:
        """Average processing time per page."""
        if not self.page_stats:
            return 0.0
        return sum(p.processing_time_seconds for p in self.page_stats) / len(self.page_stats)
    
    @property
    def avg_chars_per_page(self) -> float:
        """Average characters per page."""
        if not self.page_stats:
            return 0.0
        return sum(p.character_count for p in self.page_stats) / len(self.page_stats)
    
    @property
    def avg_words_per_page(self) -> float:
        """Average words per page."""
        if not self.page_stats:
            return 0.0
        return sum(p.word_count for p in self.page_stats) / len(self.page_stats)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data["avg_time_per_page"] = self.avg_time_per_page
        data["avg_chars_per_page"] = self.avg_chars_per_page
        data["avg_words_per_page"] = self.avg_words_per_page
        return data


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""
    timestamp: str
    model_id: str
    provider: str
    total_papers: int
    successful_papers: int
    failed_papers: int
    
    # Aggregated statistics
    total_pages_processed: int = 0
    total_time_seconds: float = 0.0
    total_characters: int = 0
    
    # Per-paper results
    papers: List[PaperBenchmark] = field(default_factory=list)
    
    @property
    def overall_avg_time_per_page(self) -> float:
        """Overall average time per page across all papers."""
        if self.total_pages_processed == 0:
            return 0.0
        return self.total_time_seconds / self.total_pages_processed
    
    @property
    def overall_avg_chars_per_page(self) -> float:
        """Overall average characters per page."""
        if self.total_pages_processed == 0:
            return 0.0
        return self.total_characters / self.total_pages_processed
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "model_id": self.model_id,
            "provider": self.provider,
            "summary": {
                "total_papers": self.total_papers,
                "successful_papers": self.successful_papers,
                "failed_papers": self.failed_papers,
                "total_pages_processed": self.total_pages_processed,
                "total_time_seconds": self.total_time_seconds,
                "total_characters": self.total_characters,
                "overall_avg_time_per_page": self.overall_avg_time_per_page,
                "overall_avg_chars_per_page": self.overall_avg_chars_per_page,
            },
            "papers": [p.to_dict() for p in self.papers],
        }


class BenchmarkRunner:
    """Runs benchmarks on PDF conversion."""
    
    def __init__(
        self,
        output_dir: str = "./benchmark_output",
        model_id: str = "Qwen/Qwen2.5-VL-7B-Instruct",
        dpi: int = 200,
    ):
        """
        Initialize the benchmark runner.
        
        Args:
            output_dir: Directory for output files
            model_id: HuggingFace model to use
            dpi: PDF rendering DPI
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.model_id = model_id
        self.dpi = dpi
        
        # Create configuration
        self.config = ConversionConfig(
            primary_provider="huggingface",
            hf_model_id=model_id,
            hf_use_inference_api=True,
            hf_api_token=HF_TOKEN,
            extract_images=False,  # Disabled for faster benchmarking
            generate_image_captions=False,
            dpi=dpi,
            request_timeout=180,  # Longer timeout for benchmark
            max_retries=3,
        )
        
        console.print(f"[bold blue]PDF-to-LaTeX Benchmark Runner[/bold blue]")
        console.print(f"Model: [cyan]{model_id}[/cyan]")
        console.print(f"Output: [cyan]{self.output_dir}[/cyan]")
        console.print()
    
    def run_benchmark(
        self,
        papers: Optional[List[Dict]] = None,
        max_pages: Optional[int] = None,
    ) -> BenchmarkReport:
        """
        Run benchmark on specified papers.
        
        Args:
            papers: List of paper configs (uses default if None)
            max_pages: Limit pages per paper (useful for testing)
        
        Returns:
            BenchmarkReport with all results
        """
        papers = papers or BENCHMARK_PAPERS
        
        report = BenchmarkReport(
            timestamp=datetime.now().isoformat(),
            model_id=self.model_id,
            provider="huggingface",
            total_papers=len(papers),
            successful_papers=0,
            failed_papers=0,
        )
        
        console.print(f"[bold]Starting benchmark of {len(papers)} papers[/bold]")
        console.print()
        
        for i, paper_config in enumerate(papers, 1):
            console.print(f"[bold cyan]Paper {i}/{len(papers)}:[/bold cyan] {paper_config['name']}")
            console.print(f"  Source: {paper_config['path'][:80]}...")
            console.print()
            
            try:
                result = self._benchmark_paper(paper_config, max_pages)
                report.papers.append(result)
                
                if result.success:
                    report.successful_papers += 1
                    report.total_pages_processed += result.total_pages
                    report.total_time_seconds += result.total_time_seconds
                    report.total_characters += result.total_characters
                    
                    self._print_paper_results(result)
                else:
                    report.failed_papers += 1
                    console.print(f"  [red]FAILED: {result.error_message}[/red]")
                    
            except Exception as e:
                report.failed_papers += 1
                console.print(f"  [red]ERROR: {str(e)}[/red]")
                
                # Create failed result
                result = PaperBenchmark(
                    name=paper_config["name"],
                    path=paper_config["path"],
                    paper_type=paper_config["type"],
                    description=paper_config["description"],
                    success=False,
                    error_message=str(e),
                )
                report.papers.append(result)
            
            console.print()
        
        return report
    
    def _benchmark_paper(
        self,
        paper_config: Dict,
        max_pages: Optional[int] = None,
    ) -> PaperBenchmark:
        """Benchmark a single paper."""
        import fitz
        
        result = PaperBenchmark(
            name=paper_config["name"],
            path=paper_config["path"],
            paper_type=paper_config["type"],
            description=paper_config["description"],
        )
        
        # Create agent
        agent = PDFToLaTeXAgent(self.config)
        
        # Track page-level timing
        page_times: List[float] = []
        page_contents: List[str] = []
        
        overall_start = time.time()
        
        try:
            # Load PDF
            download_start = time.time()
            pdf_doc = agent._load_pdf(paper_config["path"])
            result.download_time_seconds = time.time() - download_start
            
            total_pages = len(pdf_doc)
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            result.total_pages = total_pages
            
            # Render pages
            page_images = agent._render_pages(pdf_doc)[:total_pages]
            
            # Process each page with timing
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                task = progress.add_task(
                    f"Processing {total_pages} pages...",
                    total=total_pages,
                )
                
                for i, img in enumerate(page_images):
                    page_num = i + 1
                    page_start = time.time()
                    
                    content = agent._process_page(
                        img,
                        page_num=page_num,
                        total_pages=total_pages,
                        is_first_page=(i == 0),
                        is_last_page=(i == total_pages - 1),
                    )
                    
                    page_time = time.time() - page_start
                    page_times.append(page_time)
                    page_contents.append(content)
                    
                    # Calculate page stats
                    char_count = len(content)
                    word_count = len(content.split())
                    
                    # Detect content types
                    has_equations = any(x in content for x in ["\\begin{equation", "$", "\\frac", "\\sum", "\\int"])
                    has_tables = "\\begin{tabular" in content or "\\begin{table" in content
                    has_figures = "\\includegraphics" in content or "\\begin{figure" in content
                    
                    page_stat = PageStats(
                        page_number=page_num,
                        processing_time_seconds=page_time,
                        character_count=char_count,
                        word_count=word_count,
                        has_equations=has_equations,
                        has_tables=has_tables,
                        has_figures=has_figures,
                    )
                    result.page_stats.append(page_stat)
                    result.total_characters += char_count
                    result.total_words += word_count
                    
                    progress.update(task, advance=1)
            
            # Combine and generate document
            latex_body = agent._combine_pages(page_contents)
            latex_doc = agent._generate_document(latex_body)
            
            # Save output
            safe_name = "".join(c if c.isalnum() or c in "._- " else "_" for c in paper_config["name"])
            output_path = self.output_dir / f"{safe_name}.tex"
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(latex_doc)
            
            result.output_path = str(output_path)
            result.latex_size_bytes = len(latex_doc.encode("utf-8"))
            result.total_time_seconds = time.time() - overall_start
            result.success = True
            
            pdf_doc.close()
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
            result.total_time_seconds = time.time() - overall_start
            logger.error("Benchmark failed", paper=paper_config["name"], error=str(e))
        
        return result
    
    def _print_paper_results(self, result: PaperBenchmark) -> None:
        """Print results for a single paper."""
        console.print(f"  [green]SUCCESS[/green]")
        console.print(f"  Pages: {result.total_pages}")
        console.print(f"  Total time: {result.total_time_seconds:.2f}s")
        console.print(f"  Avg time/page: {result.avg_time_per_page:.2f}s")
        console.print(f"  Total chars: {result.total_characters:,}")
        console.print(f"  Avg chars/page: {result.avg_chars_per_page:.0f}")
        console.print(f"  Output: {result.output_path}")
    
    def print_summary(self, report: BenchmarkReport) -> None:
        """Print summary table of all results."""
        console.print()
        console.print("[bold blue]═══ BENCHMARK SUMMARY ═══[/bold blue]")
        console.print()
        
        # Summary table
        summary_table = Table(title="Overall Statistics")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="yellow")
        
        summary_table.add_row("Model", report.model_id)
        summary_table.add_row("Total Papers", str(report.total_papers))
        summary_table.add_row("Successful", f"[green]{report.successful_papers}[/green]")
        summary_table.add_row("Failed", f"[red]{report.failed_papers}[/red]")
        summary_table.add_row("Total Pages", str(report.total_pages_processed))
        summary_table.add_row("Total Time", f"{report.total_time_seconds:.1f}s")
        summary_table.add_row("Avg Time/Page", f"{report.overall_avg_time_per_page:.2f}s")
        summary_table.add_row("Total Characters", f"{report.total_characters:,}")
        summary_table.add_row("Avg Chars/Page", f"{report.overall_avg_chars_per_page:.0f}")
        
        console.print(summary_table)
        console.print()
        
        # Per-paper table
        paper_table = Table(title="Per-Paper Results")
        paper_table.add_column("Paper", style="cyan", max_width=35)
        paper_table.add_column("Status", justify="center")
        paper_table.add_column("Pages", justify="right")
        paper_table.add_column("Time (s)", justify="right")
        paper_table.add_column("Time/Page (s)", justify="right")
        paper_table.add_column("Chars", justify="right")
        paper_table.add_column("Chars/Page", justify="right")
        
        for paper in report.papers:
            status = "[green]✓[/green]" if paper.success else "[red]✗[/red]"
            paper_table.add_row(
                paper.name[:35],
                status,
                str(paper.total_pages) if paper.success else "-",
                f"{paper.total_time_seconds:.1f}" if paper.success else "-",
                f"{paper.avg_time_per_page:.2f}" if paper.success else "-",
                f"{paper.total_characters:,}" if paper.success else "-",
                f"{paper.avg_chars_per_page:.0f}" if paper.success else "-",
            )
        
        console.print(paper_table)
        console.print()
        
        # Page-level statistics for successful papers
        all_page_times = []
        all_page_chars = []
        
        for paper in report.papers:
            if paper.success:
                all_page_times.extend([p.processing_time_seconds for p in paper.page_stats])
                all_page_chars.extend([p.character_count for p in paper.page_stats])
        
        if all_page_times:
            stats_table = Table(title="Page-Level Statistics")
            stats_table.add_column("Metric", style="cyan")
            stats_table.add_column("Time (s)", style="yellow")
            stats_table.add_column("Characters", style="yellow")
            
            stats_table.add_row(
                "Min",
                f"{min(all_page_times):.2f}",
                f"{min(all_page_chars):,}",
            )
            stats_table.add_row(
                "Max",
                f"{max(all_page_times):.2f}",
                f"{max(all_page_chars):,}",
            )
            stats_table.add_row(
                "Mean",
                f"{statistics.mean(all_page_times):.2f}",
                f"{statistics.mean(all_page_chars):.0f}",
            )
            stats_table.add_row(
                "Median",
                f"{statistics.median(all_page_times):.2f}",
                f"{statistics.median(all_page_chars):.0f}",
            )
            if len(all_page_times) > 1:
                stats_table.add_row(
                    "Std Dev",
                    f"{statistics.stdev(all_page_times):.2f}",
                    f"{statistics.stdev(all_page_chars):.0f}",
                )
            
            console.print(stats_table)
    
    def save_report(self, report: BenchmarkReport, filename: str = "benchmark_report.json") -> str:
        """Save benchmark report to JSON file."""
        report_path = self.output_dir / filename
        
        with open(report_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        
        console.print(f"\n[bold green]Report saved to:[/bold green] {report_path}")
        return str(report_path)


def main():
    """Run the benchmark."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Benchmark PDF-to-LaTeX conversion")
    parser.add_argument(
        "--output-dir", "-o",
        default="./benchmark_output",
        help="Output directory for results",
    )
    parser.add_argument(
        "--model", "-m",
        default="Qwen/Qwen2.5-VL-7B-Instruct",
        help="HuggingFace model ID",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limit pages per paper (for testing)",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=200,
        help="PDF rendering DPI",
    )
    parser.add_argument(
        "--papers",
        type=int,
        default=None,
        help="Limit number of papers to test",
    )
    
    args = parser.parse_args()
    
    # Create runner
    runner = BenchmarkRunner(
        output_dir=args.output_dir,
        model_id=args.model,
        dpi=args.dpi,
    )
    
    # Select papers
    papers = BENCHMARK_PAPERS
    if args.papers:
        papers = papers[:args.papers]
    
    # Run benchmark
    report = runner.run_benchmark(papers, max_pages=args.max_pages)
    
    # Print summary
    runner.print_summary(report)
    
    # Save report
    runner.save_report(report)
    
    console.print("\n[bold green]Benchmark complete![/bold green]")
    
    # Return exit code based on success rate
    if report.failed_papers > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
