"""
Command-line interface for PDF-to-LaTeX conversion.

Provides CLI commands for:
- Converting single or multiple PDFs
- Starting the API server
- Running Celery workers
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="pdf-to-latex",
    help="Convert PDF documents to LaTeX using Vision Language Models",
    add_completion=False,
)
console = Console()


@app.command()
def convert(
    input_path: str = typer.Argument(..., help="Path to PDF file or URL"),
    output: Optional[str] = typer.Option(
        None, "-o", "--output", help="Output .tex file path"
    ),
    extract_images: bool = typer.Option(
        True, "--images/--no-images", help="Extract images from PDF"
    ),
    document_class: str = typer.Option(
        "article", "-c", "--class", help="LaTeX document class"
    ),
    model: str = typer.Option(
        None, "-m", "--model", help="Model ID (HuggingFace or Ollama model name)"
    ),
    local: bool = typer.Option(
        False, "--local", help="Use local GPU inference with HuggingFace Transformers"
    ),
    ollama: bool = typer.Option(
        False, "--ollama", help="Use Ollama for completely local inference (no API needed)"
    ),
    ollama_host: str = typer.Option(
        "http://localhost:11434", "--ollama-host", help="Ollama server URL"
    ),
    provider: str = typer.Option(
        None, "-p", "--provider", help="Provider: huggingface, ollama, openai, google"
    ),
    dpi: int = typer.Option(200, "--dpi", help="PDF rendering DPI"),
):
    """
    Convert a PDF file to LaTeX.
    
    Examples:
        # Using Hugging Face Inference API (requires HF_TOKEN)
        pdf-to-latex convert paper.pdf -o paper.tex
        pdf-to-latex convert paper.pdf --model nanonets/Nanonets-OCR-s
        
        # Using Ollama (completely local, no API needed)
        pdf-to-latex convert paper.pdf --ollama
        pdf-to-latex convert paper.pdf --ollama --model llava:13b
        pdf-to-latex convert paper.pdf --ollama --model bakllava
        
        # Using local HuggingFace Transformers (requires GPU)
        pdf-to-latex convert paper.pdf --local
    """
    from app.config import ConversionConfig
    from app.converter.agent import PDFToLaTeXAgent

    # Determine output path
    if output is None:
        input_file = Path(input_path).stem if not input_path.startswith("http") else "output"
        output = f"{input_file}.tex"

    # Determine provider
    if provider:
        selected_provider = provider.lower()
    elif ollama:
        selected_provider = "ollama"
    elif local:
        selected_provider = "huggingface"
    else:
        selected_provider = "huggingface"

    # Determine model
    if model is None:
        if selected_provider == "ollama":
            model = "llava:13b"
        else:
            model = "Qwen/Qwen2.5-VL-7B-Instruct"

    console.print(f"[bold blue]PDF-to-LaTeX Converter[/bold blue]")
    console.print(f"Input: {input_path}")
    console.print(f"Output: {output}")
    console.print(f"Provider: [cyan]{selected_provider}[/cyan]")
    console.print(f"Model: [cyan]{model}[/cyan]")
    if selected_provider == "ollama":
        console.print(f"Ollama Host: [cyan]{ollama_host}[/cyan]")
    console.print()

    # Create configuration
    config = ConversionConfig(
        extract_images=extract_images,
        document_class=document_class,
        primary_provider=selected_provider,
        hf_model_id=model if selected_provider == "huggingface" else "Qwen/Qwen2.5-VL-7B-Instruct",
        hf_use_inference_api=not local and selected_provider == "huggingface",
        ollama_model=model if selected_provider == "ollama" else "llava:13b",
        ollama_host=ollama_host,
        dpi=dpi,
    )

    # Progress tracking
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Initializing...", total=None)

        try:
            agent = PDFToLaTeXAgent(config)

            def on_progress(page: int, total: int):
                progress.update(
                    task, description=f"Processing page {page}/{total}..."
                )

            agent.on_progress = on_progress

            progress.update(task, description="Converting PDF...")
            latex = agent.convert(input_path, output)

            progress.update(task, description="Done!")

        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

    console.print()
    console.print(f"[bold green]✓[/bold green] Conversion complete!")
    console.print(f"  Output saved to: [cyan]{output}[/cyan]")
    console.print(f"  LaTeX size: {len(latex):,} characters")


@app.command()
def batch(
    input_dir: str = typer.Argument(..., help="Directory containing PDF files"),
    output_dir: str = typer.Option(
        "./output", "-o", "--output-dir", help="Output directory"
    ),
    pattern: str = typer.Option("*.pdf", "-p", "--pattern", help="File pattern"),
    workers: int = typer.Option(4, "-w", "--workers", help="Parallel workers"),
):
    """
    Convert multiple PDF files in a directory.
    
    Example:
        pdf-to-latex batch ./papers -o ./latex_output -w 2
    """
    from app.config import ConversionConfig
    from app.converter.agent import BatchConverter

    input_path = Path(input_dir)
    if not input_path.exists():
        console.print(f"[bold red]Error:[/bold red] Directory not found: {input_dir}")
        raise typer.Exit(1)

    pdf_files = list(input_path.glob(pattern))
    if not pdf_files:
        console.print(f"[yellow]No PDF files found matching pattern: {pattern}[/yellow]")
        raise typer.Exit(0)

    console.print(f"[bold blue]Batch PDF-to-LaTeX Converter[/bold blue]")
    console.print(f"Found {len(pdf_files)} PDF files")
    console.print()

    config = ConversionConfig()
    converter = BatchConverter(config, max_workers=workers)

    with Progress(console=console) as progress:
        task = progress.add_task("Converting...", total=len(pdf_files))

        results = converter.convert_batch(
            [str(f) for f in pdf_files], output_dir
        )

        progress.update(task, completed=len(pdf_files))

    # Show results
    table = Table(title="Conversion Results")
    table.add_column("File", style="cyan")
    table.add_column("Status", style="green")

    success_count = 0
    for path, result in results.items():
        status = "✓ Success" if result == "SUCCESS" else f"✗ {result}"
        style = "green" if result == "SUCCESS" else "red"
        table.add_row(Path(path).name, f"[{style}]{status}[/{style}]")
        if result == "SUCCESS":
            success_count += 1

    console.print(table)
    console.print()
    console.print(f"Completed: {success_count}/{len(pdf_files)} successful")


@app.command()
def info():
    """
    Show configuration and environment information.
    """
    import os
    from app.config import settings, RECOMMENDED_MODELS, OLLAMA_MODELS

    console.print("[bold blue]PDF-to-LaTeX Configuration[/bold blue]")
    console.print()

    # Environment
    table = Table(title="Environment & API Keys")
    table.add_column("Variable", style="cyan")
    table.add_column("Status", style="green")

    hf_token = "✓ Set" if os.environ.get("HF_TOKEN") else "✗ Not set"
    table.add_row("HF_TOKEN", hf_token)

    openai_key = "✓ Set" if os.environ.get("OPENAI_API_KEY") else "✗ Not set"
    table.add_row("OPENAI_API_KEY", openai_key)

    google_key = "✓ Set" if os.environ.get("GOOGLE_API_KEY") else "✗ Not set"
    table.add_row("GOOGLE_API_KEY", google_key)

    # Check Ollama availability
    ollama_status = "✗ Not available"
    try:
        from app.ocr.ollama_client import OllamaOCRClient
        client = OllamaOCRClient()
        if client.is_available():
            ollama_status = "✓ Running"
        else:
            ollama_status = "⚠ Running but model not pulled"
    except Exception:
        pass
    table.add_row("Ollama", ollama_status)

    console.print(table)
    console.print()

    # Settings
    table = Table(title="Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("HF Model ID", settings.HF_MODEL_ID)
    table.add_row("Use Inference API", str(settings.HF_USE_INFERENCE_API))
    table.add_row("Ollama Host", settings.OLLAMA_HOST)
    table.add_row("Ollama Model", settings.OLLAMA_MODEL)
    table.add_row("Upload Dir", settings.UPLOAD_DIR)
    table.add_row("Output Dir", settings.OUTPUT_DIR)
    table.add_row("DPI", str(settings.DPI))
    table.add_row("Max File Size", f"{settings.MAX_FILE_SIZE_MB} MB")

    console.print(table)
    console.print()

    # HuggingFace Models
    table = Table(title="Recommended HuggingFace Models (requires API)")
    table.add_column("Use Case", style="cyan")
    table.add_column("Model ID", style="yellow")

    for use_case, model_id in RECOMMENDED_MODELS.items():
        table.add_row(use_case.capitalize(), model_id)

    console.print(table)
    console.print()

    # Ollama Models
    table = Table(title="Recommended Ollama Models (local, no API)")
    table.add_column("Use Case", style="cyan")
    table.add_column("Model Name", style="yellow")

    for use_case, model_id in OLLAMA_MODELS.items():
        table.add_row(use_case.capitalize(), model_id)

    console.print(table)


@app.command()
def models(
    provider: str = typer.Option(
        "all", "-p", "--provider", help="Filter by provider: huggingface, ollama, all"
    ),
):
    """
    List available and recommended models.
    
    Examples:
        pdf-to-latex models
        pdf-to-latex models --provider ollama
        pdf-to-latex models --provider huggingface
    """
    from app.config import RECOMMENDED_MODELS, OLLAMA_MODELS

    console.print("[bold blue]Available Models[/bold blue]")
    console.print()

    if provider in ("all", "huggingface"):
        table = Table(title="HuggingFace Models (Cloud API)")
        table.add_column("Use Case", style="cyan")
        table.add_column("Model ID", style="yellow")
        table.add_column("Notes", style="dim")

        notes = {
            "general": "Recommended for most documents",
            "equations": "Best for math-heavy papers",
            "tables": "Specialized for table extraction",
            "formatted": "Good for formatted text",
            "fast": "Fastest, lower quality",
        }

        for use_case, model_id in RECOMMENDED_MODELS.items():
            table.add_row(use_case.capitalize(), model_id, notes.get(use_case, ""))

        console.print(table)
        console.print()
        console.print("[dim]Usage: pdf-to-latex convert paper.pdf --model MODEL_ID[/dim]")
        console.print()

    if provider in ("all", "ollama"):
        table = Table(title="Ollama Models (Local, No API)")
        table.add_column("Use Case", style="cyan")
        table.add_column("Model Name", style="yellow")
        table.add_column("Notes", style="dim")

        notes = {
            "general": "13B - Good balance (recommended)",
            "fast": "7B - Faster, less VRAM",
            "quality": "34B - Best quality, needs 24GB+ VRAM",
            "bakllava": "Good for documents",
            "llava-llama3": "LLaVA with Llama 3",
            "minicpm-v": "Efficient vision model",
            "moondream": "Very lightweight",
        }

        for use_case, model_id in OLLAMA_MODELS.items():
            table.add_row(use_case.capitalize(), model_id, notes.get(use_case, ""))

        console.print(table)
        console.print()
        console.print("[dim]Usage: pdf-to-latex convert paper.pdf --ollama --model MODEL_NAME[/dim]")
        console.print()

        # List locally available Ollama models
        try:
            from app.ocr.ollama_client import OllamaOCRClient
            client = OllamaOCRClient()
            local_models = client.list_models()
            
            if local_models:
                console.print("[bold green]Locally Available Ollama Models:[/bold green]")
                for m in local_models:
                    console.print(f"  • {m}")
            else:
                console.print("[yellow]No Ollama models installed locally.[/yellow]")
                console.print("[dim]Pull a model with: ollama pull llava:13b[/dim]")
        except Exception:
            console.print("[yellow]Ollama not running or not installed.[/yellow]")
            console.print("[dim]Install from: https://ollama.ai/download[/dim]")


@app.command()
def pull(
    model: str = typer.Argument("llava:13b", help="Ollama model to pull"),
):
    """
    Pull/download an Ollama model for local inference.
    
    Examples:
        pdf-to-latex pull llava:13b
        pdf-to-latex pull bakllava
        pdf-to-latex pull llava:7b
    """
    console.print(f"[bold blue]Pulling Ollama model: {model}[/bold blue]")
    
    try:
        from app.ocr.ollama_client import OllamaOCRClient
        client = OllamaOCRClient(model=model)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Pulling {model}...", total=None)
            
            success = client.pull_model()
            
            if success:
                progress.update(task, description="Done!")
                console.print(f"[bold green]✓[/bold green] Model {model} is ready!")
                console.print()
                console.print(f"[dim]Use with: pdf-to-latex convert paper.pdf --ollama --model {model}[/dim]")
            else:
                console.print(f"[bold red]✗[/bold red] Failed to pull model")
                raise typer.Exit(1)
                
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        console.print()
        console.print("[dim]Make sure Ollama is installed and running.[/dim]")
        console.print("[dim]Install from: https://ollama.ai/download[/dim]")
        raise typer.Exit(1)


@app.command()
def validate(
    pdf_path: str = typer.Argument(..., help="Path to original PDF file"),
    latex_path: str = typer.Argument(..., help="Path to generated LaTeX file"),
    output: Optional[str] = typer.Option(
        None, "-o", "--output", help="Save report to JSON file"
    ),
    brief: bool = typer.Option(
        False, "-b", "--brief", help="Show brief summary only"
    ),
):
    """
    Validate conversion quality by comparing PDF and LaTeX.
    
    Compares word counts, character counts, structure, and vocabulary
    between the original PDF and generated LaTeX to assess conversion quality.
    
    Examples:
        pdf-to-latex validate paper.pdf paper.tex
        pdf-to-latex validate paper.pdf paper.tex --brief
        pdf-to-latex validate paper.pdf paper.tex -o report.json
    """
    from app.converter.validator import ConversionValidator
    import json
    
    console.print("[bold blue]PDF-to-LaTeX Conversion Validator[/bold blue]")
    console.print()
    
    # Validate paths
    if not Path(pdf_path).exists():
        console.print(f"[bold red]Error:[/bold red] PDF file not found: {pdf_path}")
        raise typer.Exit(1)
    
    if not Path(latex_path).exists():
        console.print(f"[bold red]Error:[/bold red] LaTeX file not found: {latex_path}")
        raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing documents...", total=None)
        
        validator = ConversionValidator()
        report = validator.validate(pdf_path, latex_path)
        
        progress.update(task, description="Done!")
    
    console.print()
    
    # Get statistics reference
    stats = report.statistics
    
    if brief:
        # Brief summary
        table = Table(title="Statistical Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("PDF", style="yellow")
        table.add_column("LaTeX", style="yellow")
        table.add_column("Difference", style="yellow")
        
        table.add_row(
            "Words", 
            f"{stats.pdf_total_words:,}", 
            f"{stats.latex_total_words:,}",
            f"{stats.word_difference:+,}"
        )
        table.add_row(
            "Characters", 
            f"{stats.pdf_total_chars:,}", 
            f"{stats.latex_total_chars:,}",
            f"{stats.char_difference:+,}"
        )
        table.add_row(
            "Equations (est.)", 
            f"{stats.pdf_equations_estimated}", 
            f"{stats.latex_total_equations}",
            f"{stats.equation_difference:+d}"
        )
        table.add_row(
            "Tables", 
            f"{stats.pdf_tables_detected}", 
            f"{stats.latex_tables}",
            f"{stats.table_difference:+d}"
        )
        table.add_row(
            "Figures", 
            f"{stats.pdf_figures_detected}", 
            f"{stats.latex_figures}",
            f"{stats.figure_difference:+d}"
        )
        table.add_row(
            "Sections", 
            f"{stats.pdf_sections_estimated}", 
            f"{stats.latex_total_sections}",
            f"{stats.section_difference:+d}"
        )
        
        console.print(table)
        console.print()
        
        # Coverage percentages
        console.print(f"Word Coverage:      {stats.word_coverage_pct:.1f}%")
        console.print(f"Character Coverage: {stats.char_coverage_pct:.1f}%")
        console.print(f"Vocabulary Overlap: {report.vocabulary.vocabulary_overlap_pct:.1f}%")
        console.print(f"Numbers Matched:    {report.vocabulary.numbers_matched_pct:.1f}%")
        
        # Missing items
        if stats.missing_tables:
            console.print(f"\nMissing tables: {', '.join(stats.missing_tables)}")
        if stats.missing_figures:
            console.print(f"Missing figures: {', '.join(stats.missing_figures[:5])}")
        if report.vocabulary.missing_key_terms:
            console.print(f"Missing terms: {', '.join(report.vocabulary.missing_key_terms[:5])}")
        
        if report.warnings:
            console.print()
            console.print("[yellow]Warnings:[/yellow]")
            for w in report.warnings:
                console.print(f"  - {w}")
        
        if report.critical_issues:
            console.print()
            console.print("[red]Critical Issues:[/red]")
            for e in report.critical_issues:
                console.print(f"  - {e}")
    else:
        # Full report
        console.print(validator.print_report(report))
    
    # Save to JSON if requested
    if output:
        report_dict = report.to_dict()
        with open(output, "w") as f:
            json.dump(report_dict, f, indent=2)
        console.print(f"\nReport saved to: {output}")
    
    # Exit code based on coverage
    if stats.word_coverage_pct < 50:
        console.print("\nResult: LOW COVERAGE - significant content missing")
        raise typer.Exit(2)
    elif stats.word_coverage_pct < 70:
        console.print("\nResult: PARTIAL COVERAGE - some content may be missing")
        raise typer.Exit(1)
    else:
        console.print("\nResult: GOOD COVERAGE")


@app.command()
def compare(
    pdf_path: str = typer.Argument(..., help="Path to original PDF file"),
    latex_path: str = typer.Argument(..., help="Path to generated LaTeX file"),
    page: int = typer.Option(
        None, "-p", "--page", help="Compare specific page only"
    ),
):
    """
    Show detailed page-by-page comparison between PDF and LaTeX.
    
    Examples:
        pdf-to-latex compare paper.pdf paper.tex
        pdf-to-latex compare paper.pdf paper.tex --page 3
    """
    from app.converter.validator import ConversionValidator
    
    console.print("[bold blue]PDF-to-LaTeX Page Comparison[/bold blue]")
    console.print()
    
    # Validate paths
    if not Path(pdf_path).exists():
        console.print(f"[bold red]Error:[/bold red] PDF file not found: {pdf_path}")
        raise typer.Exit(1)
    
    if not Path(latex_path).exists():
        console.print(f"[bold red]Error:[/bold red] LaTeX file not found: {latex_path}")
        raise typer.Exit(1)
    
    validator = ConversionValidator()
    report = validator.validate(pdf_path, latex_path, per_page=True)
    
    if not report.block_stats:
        console.print("[yellow]No page-by-page data available[/yellow]")
        raise typer.Exit(1)
    
    # Filter to specific page if requested
    stats_to_show = report.block_stats
    if page:
        stats_to_show = [s for s in report.block_stats if s.block_id == page]
        if not stats_to_show:
            console.print(f"[red]Page {page} not found[/red]")
            raise typer.Exit(1)
    
    # Create detailed table
    table = Table(title=f"Page-by-Page Comparison ({len(stats_to_show)} pages)")
    table.add_column("Page", style="cyan", justify="right")
    table.add_column("PDF Words", justify="right")
    table.add_column("LaTeX Words", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("PDF Chars", justify="right")
    table.add_column("LaTeX Chars", justify="right")
    table.add_column("Char Cov.", justify="right")
    table.add_column("Sections", justify="right")
    table.add_column("Math", justify="center")
    table.add_column("Status", justify="center")
    
    for stat in stats_to_show:
        # Determine status
        if stat.word_coverage >= 0.7 and stat.word_coverage <= 1.3:
            status = "[green]✓[/green]"
        elif stat.word_coverage >= 0.5 and stat.word_coverage <= 1.5:
            status = "[yellow]~[/yellow]"
        else:
            status = "[red]⚠[/red]"
        
        table.add_row(
            str(stat.block_id),
            f"{stat.pdf_word_count:,}",
            f"{stat.latex_word_count:,}",
            f"{stat.word_coverage:.1%}",
            f"{stat.pdf_char_count:,}",
            f"{stat.latex_char_count:,}",
            f"{stat.char_coverage:.1%}",
            str(stat.sections_detected),
            "Yes" if stat.has_math else "No",
            status,
        )
    
    console.print(table)
    
    # Summary
    console.print()
    avg_coverage = sum(s.word_coverage for s in stats_to_show) / len(stats_to_show)
    good_pages = sum(1 for s in stats_to_show if 0.7 <= s.word_coverage <= 1.3)
    
    console.print(f"Average word coverage: [cyan]{avg_coverage:.1%}[/cyan]")
    console.print(f"Pages with good coverage (70-130%): [cyan]{good_pages}/{len(stats_to_show)}[/cyan]")
    
    # Flag problematic pages
    problem_pages = [s.block_id for s in stats_to_show if s.word_coverage < 0.5 or s.word_coverage > 1.5]
    if problem_pages:
        console.print(f"\n[yellow]Pages needing attention: {problem_pages}[/yellow]")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

