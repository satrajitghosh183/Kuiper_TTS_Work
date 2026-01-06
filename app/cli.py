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
        "Qwen/Qwen2.5-VL-7B-Instruct", "-m", "--model", help="Hugging Face model ID"
    ),
    local: bool = typer.Option(
        False, "--local", help="Use local GPU inference instead of API"
    ),
    dpi: int = typer.Option(200, "--dpi", help="PDF rendering DPI"),
):
    """
    Convert a PDF file to LaTeX.
    
    Examples:
        pdf-to-latex convert paper.pdf -o paper.tex
        pdf-to-latex convert https://example.com/paper.pdf --no-images
        pdf-to-latex convert paper.pdf --model nanonets/Nanonets-OCR-s
    """
    from app.config import ConversionConfig
    from app.converter.agent import PDFToLaTeXAgent

    # Determine output path
    if output is None:
        input_file = Path(input_path).stem if not input_path.startswith("http") else "output"
        output = f"{input_file}.tex"

    console.print(f"[bold blue]PDF-to-LaTeX Converter[/bold blue]")
    console.print(f"Input: {input_path}")
    console.print(f"Output: {output}")
    console.print()

    # Create configuration
    config = ConversionConfig(
        extract_images=extract_images,
        document_class=document_class,
        hf_model_id=model,
        hf_use_inference_api=not local,
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
def serve(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind"),
    port: int = typer.Option(8000, "--port", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
    workers: int = typer.Option(1, "-w", "--workers", help="Number of workers"),
):
    """
    Start the API server.
    
    Example:
        pdf-to-latex serve --port 8080 --reload
    """
    import uvicorn

    console.print(f"[bold blue]Starting PDF-to-LaTeX API Server[/bold blue]")
    console.print(f"Host: {host}:{port}")
    console.print(f"Docs: http://{host}:{port}/docs")
    console.print()

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers if not reload else 1,
        log_level="info",
    )


@app.command()
def worker(
    concurrency: int = typer.Option(2, "-c", "--concurrency", help="Worker concurrency"),
    queues: str = typer.Option("celery", "-Q", "--queues", help="Queue names"),
    loglevel: str = typer.Option("info", "-l", "--loglevel", help="Log level"),
):
    """
    Start a Celery worker.
    
    Example:
        pdf-to-latex worker -c 4 -l debug
    """
    import subprocess

    console.print(f"[bold blue]Starting Celery Worker[/bold blue]")
    console.print(f"Concurrency: {concurrency}")
    console.print(f"Queues: {queues}")
    console.print()

    cmd = [
        "celery",
        "-A", "app.worker",
        "worker",
        f"--concurrency={concurrency}",
        f"-Q", queues,
        f"--loglevel={loglevel}",
    ]

    subprocess.run(cmd)


@app.command()
def info():
    """
    Show configuration and environment information.
    """
    import os
    from app.config import settings, RECOMMENDED_MODELS

    console.print("[bold blue]PDF-to-LaTeX Configuration[/bold blue]")
    console.print()

    # Environment
    table = Table(title="Environment")
    table.add_column("Variable", style="cyan")
    table.add_column("Status", style="green")

    hf_token = "✓ Set" if os.environ.get("HF_TOKEN") else "✗ Not set"
    table.add_row("HF_TOKEN", hf_token)

    openai_key = "✓ Set" if os.environ.get("OPENAI_API_KEY") else "✗ Not set"
    table.add_row("OPENAI_API_KEY", openai_key)

    google_key = "✓ Set" if os.environ.get("GOOGLE_API_KEY") else "✗ Not set"
    table.add_row("GOOGLE_API_KEY", google_key)

    console.print(table)
    console.print()

    # Settings
    table = Table(title="Settings")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Model ID", settings.HF_MODEL_ID)
    table.add_row("Use Inference API", str(settings.HF_USE_INFERENCE_API))
    table.add_row("Redis URL", settings.REDIS_URL)
    table.add_row("Upload Dir", settings.UPLOAD_DIR)
    table.add_row("Output Dir", settings.OUTPUT_DIR)
    table.add_row("DPI", str(settings.DPI))
    table.add_row("Max File Size", f"{settings.MAX_FILE_SIZE_MB} MB")

    console.print(table)
    console.print()

    # Models
    table = Table(title="Recommended Models")
    table.add_column("Use Case", style="cyan")
    table.add_column("Model ID", style="yellow")

    for use_case, model_id in RECOMMENDED_MODELS.items():
        table.add_row(use_case.capitalize(), model_id)

    console.print(table)


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()

