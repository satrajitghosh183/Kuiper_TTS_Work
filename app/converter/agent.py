"""
Core PDF-to-LaTeX conversion agent.

This module provides the main agent that orchestrates the full conversion pipeline:
1. PDF ingestion (file or URL)
2. Page-by-page processing with VLM
3. Structure analysis and reconstruction
4. LaTeX generation and validation
5. Optional image extraction
"""

from __future__ import annotations

import io
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

import requests
import structlog
from PIL import Image

from app.config import ConversionConfig
from app.converter.latex_utils import (
    LaTeXCleaner,
    LaTeXDocumentGenerator,
    LaTeXValidator,
)
from app.exceptions import (
    ConversionError,
    FileError,
    ImageExtractionError,
    OCRError,
    PDFParseError,
)
from app.models import PageContent
from app.ocr.hf_client import HuggingFaceOCRClient
from app.ocr.local_client import LocalHuggingFaceOCR
from app.ocr.prompts import get_page_conversion_prompt

logger = structlog.get_logger()


class PDFToLaTeXAgent:
    """
    Autonomous agent for converting PDF documents to LaTeX.

    This agent orchestrates the full conversion pipeline:
    1. PDF ingestion (file or URL)
    2. Page-by-page processing with VLM
    3. Structure analysis and reconstruction
    4. LaTeX generation and validation
    5. Optional image extraction

    Example:
        >>> config = ConversionConfig()
        >>> agent = PDFToLaTeXAgent(config)
        >>> latex = agent.convert("paper.pdf", "output/paper.tex")

    Attributes:
        config: Conversion configuration
        on_progress: Optional callback for progress updates
    """

    def __init__(self, config: Optional[ConversionConfig] = None):
        """
        Initialize the PDF-to-LaTeX agent.

        Args:
            config: Conversion configuration. Uses defaults if None.
        """
        self.config = config or ConversionConfig()
        self.on_progress: Optional[Callable[[int, int], None]] = None
        self._ocr_client = None

        self._init_clients()

        logger.info(
            "Initialized PDFToLaTeXAgent",
            parser_type=self.config.parser_type,
            extract_images=self.config.extract_images,
            provider=self.config.primary_provider,
        )

    def _init_clients(self) -> None:
        """Initialize API clients based on configuration."""
        if self.config.primary_provider == "huggingface":
            if self.config.hf_use_inference_api:
                try:
                    self._ocr_client = HuggingFaceOCRClient(
                        model_id=self.config.hf_model_id,
                        token=self.config.hf_api_token,
                        timeout=self.config.request_timeout,
                        max_retries=self.config.max_retries,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to initialize HF Inference API client",
                        error=str(e),
                    )
            else:
                try:
                    self._ocr_client = LocalHuggingFaceOCR(
                        model_id=self.config.hf_model_id,
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to initialize local HF client",
                        error=str(e),
                    )

    @property
    def ocr_client(self):
        """Get the OCR client, initializing if needed."""
        if self._ocr_client is None:
            raise ConversionError(
                "No OCR client available. Check API configuration and credentials."
            )
        return self._ocr_client

    def convert(
        self,
        input_path: str,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Convert PDF to LaTeX.

        Args:
            input_path: Path to PDF file or URL
            output_path: Optional output .tex file path

        Returns:
            LaTeX source code as string

        Raises:
            ConversionError: If conversion fails
            PDFParseError: If PDF cannot be parsed
        """
        logger.info("Starting PDF conversion", input_path=input_path)

        try:
            # Import fitz here to allow graceful failure if not installed
            import fitz
        except ImportError:
            raise ConversionError(
                "PyMuPDF (fitz) is required for PDF processing. "
                "Install with: pip install PyMuPDF"
            )

        # Step 1: Load PDF
        pdf_doc = self._load_pdf(input_path)
        total_pages = len(pdf_doc)
        logger.info("PDF loaded", pages=total_pages)

        # Step 2: Extract pages as images
        page_images = self._render_pages(pdf_doc)

        # Step 3: Process each page
        page_contents = []
        for i, img in enumerate(page_images):
            page_num = i + 1
            logger.info(f"Processing page {page_num}/{total_pages}")

            if self.on_progress:
                self.on_progress(page_num, total_pages)

            content = self._process_page(
                img,
                page_num=page_num,
                total_pages=total_pages,
                is_first_page=(i == 0),
                is_last_page=(i == total_pages - 1),
            )
            page_contents.append(content)

        # Step 4: Combine and structure
        latex_body = self._combine_pages(page_contents)

        # Step 5: Generate complete document
        latex_doc = self._generate_document(latex_body)

        # Step 6: Extract images if enabled
        if self.config.extract_images and output_path:
            try:
                self._extract_images(pdf_doc, output_path)
            except Exception as e:
                logger.warning("Image extraction failed", error=str(e))

        # Step 7: Validate and save
        if output_path:
            self._validate_and_save(latex_doc, output_path)

        pdf_doc.close()

        logger.info("Conversion completed", output_path=output_path)
        return latex_doc

    def convert_bytes(
        self,
        pdf_bytes: bytes,
        output_path: Optional[str] = None,
    ) -> str:
        """
        Convert PDF from bytes to LaTeX.

        Args:
            pdf_bytes: PDF file content as bytes
            output_path: Optional output .tex file path

        Returns:
            LaTeX source code as string
        """
        try:
            import fitz
        except ImportError:
            raise ConversionError("PyMuPDF (fitz) is required.")

        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")

        # Process similarly to convert()
        total_pages = len(pdf_doc)
        page_images = self._render_pages(pdf_doc)

        page_contents = []
        for i, img in enumerate(page_images):
            page_num = i + 1
            if self.on_progress:
                self.on_progress(page_num, total_pages)

            content = self._process_page(
                img,
                page_num=page_num,
                total_pages=total_pages,
                is_first_page=(i == 0),
                is_last_page=(i == total_pages - 1),
            )
            page_contents.append(content)

        latex_body = self._combine_pages(page_contents)
        latex_doc = self._generate_document(latex_body)

        if output_path:
            self._validate_and_save(latex_doc, output_path)

        pdf_doc.close()
        return latex_doc

    def _load_pdf(self, path: str):
        """
        Load PDF from file path or URL.

        Args:
            path: File path or URL

        Returns:
            fitz.Document object
        """
        import fitz

        try:
            if path.startswith(("http://", "https://")):
                logger.info("Downloading PDF from URL", url=path)
                response = requests.get(path, timeout=60)
                response.raise_for_status()
                return fitz.open(stream=response.content, filetype="pdf")

            if not os.path.exists(path):
                raise FileError(f"PDF file not found: {path}")

            return fitz.open(path)

        except requests.RequestException as e:
            raise PDFParseError(f"Failed to download PDF: {e}")
        except Exception as e:
            raise PDFParseError(f"Failed to open PDF: {e}")

    def _render_pages(self, doc) -> List[Image.Image]:
        """
        Render PDF pages to images.

        Args:
            doc: fitz.Document object

        Returns:
            List of PIL Image objects
        """
        import fitz

        images = []
        dpi_scale = self.config.dpi / 72

        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render at specified DPI
            mat = fitz.Matrix(dpi_scale, dpi_scale)
            pix = page.get_pixmap(matrix=mat)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)

        return images

    def _process_page(
        self,
        image: Image.Image,
        page_num: int,
        total_pages: int,
        is_first_page: bool = False,
        is_last_page: bool = False,
    ) -> str:
        """
        Process a single page image with the VLM.

        Args:
            image: PIL Image object
            page_num: Current page number (1-indexed)
            total_pages: Total number of pages
            is_first_page: Whether this is the first page
            is_last_page: Whether this is the last page

        Returns:
            LaTeX content for this page
        """
        prompt = get_page_conversion_prompt(
            page_num=page_num,
            total_pages=total_pages,
            extract_images=self.config.extract_images,
            is_first_page=is_first_page,
            is_last_page=is_last_page,
        )

        try:
            content = self.ocr_client.ocr_image(image, prompt=prompt)
            return LaTeXCleaner.clean(content)
        except Exception as e:
            logger.error(
                "Failed to process page",
                page_num=page_num,
                error=str(e),
            )
            raise OCRError(f"Failed to process page {page_num}: {e}")

    def _combine_pages(self, pages: List[str]) -> str:
        """
        Combine page contents into coherent document body.

        Args:
            pages: List of LaTeX content from each page

        Returns:
            Combined document body
        """
        # Join pages with page break comments
        combined = "\n\n% --- Page Break ---\n\n".join(pages)

        # Clean up the combined content
        combined = LaTeXCleaner.clean(combined)

        # Fix any remaining issues
        combined = LaTeXCleaner.fix_braces(combined)
        combined = LaTeXCleaner.fix_environments(combined)

        return combined

    def _generate_document(self, body: str) -> str:
        """
        Generate complete LaTeX document with preamble.

        Args:
            body: Document body content

        Returns:
            Complete LaTeX document
        """
        graphics_path = None
        if self.config.extract_images:
            graphics_path = self.config.image_output_dir

        return LaTeXDocumentGenerator.generate_document(
            body=body,
            document_class=self.config.document_class,
            packages=self.config.use_packages,
            graphics_path=graphics_path,
        )

    def _extract_images(
        self,
        doc,
        output_base: str,
    ) -> List[str]:
        """
        Extract images from PDF (TOGGLEABLE FEATURE).

        This feature can be enabled/disabled via config.extract_images

        Args:
            doc: fitz.Document object
            output_base: Base path for output

        Returns:
            List of extracted image paths
        """
        if not self.config.extract_images:
            return []

        output_dir = Path(output_base).parent / self.config.image_output_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted = []
        img_counter = 0

        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images()

            for img_index, img in enumerate(image_list):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Determine format
                    img_ext = base_image.get("ext", self.config.image_format)
                    if img_ext not in ("png", "jpg", "jpeg", "pdf"):
                        img_ext = self.config.image_format

                    # Save image
                    img_counter += 1
                    filename = f"figure_{page_num + 1}_{img_counter}.{img_ext}"
                    filepath = output_dir / filename

                    with open(filepath, "wb") as f:
                        f.write(image_bytes)

                    extracted.append(str(filepath))
                    logger.debug("Extracted image", path=str(filepath))

                    # Generate caption if enabled
                    if self.config.generate_image_captions:
                        try:
                            caption = self._generate_caption(filepath)
                            caption_file = filepath.with_suffix(".caption.txt")
                            caption_file.write_text(caption)
                        except Exception as e:
                            logger.warning(
                                "Failed to generate caption",
                                image=str(filepath),
                                error=str(e),
                            )

                except Exception as e:
                    logger.warning(
                        "Failed to extract image",
                        page=page_num + 1,
                        index=img_index,
                        error=str(e),
                    )

        logger.info("Image extraction complete", count=len(extracted))
        return extracted

    def _generate_caption(self, image_path: Union[str, Path]) -> str:
        """
        Use VLM to generate image caption.

        Args:
            image_path: Path to image file

        Returns:
            Generated caption text
        """
        from app.ocr.prompts import FIGURE_CAPTION_PROMPT

        img = Image.open(image_path)
        return self.ocr_client.ocr_image(
            img, prompt=FIGURE_CAPTION_PROMPT, output_format="plain"
        )

    def _validate_and_save(self, latex: str, output_path: str) -> None:
        """
        Validate LaTeX compilation and save.

        Args:
            latex: Complete LaTeX document
            output_path: Path to save .tex file
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Validate syntax
        is_valid, errors = LaTeXValidator.validate_syntax(latex)
        if not is_valid:
            logger.warning("LaTeX syntax issues detected", errors=errors)

        # Save .tex file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latex)

        logger.info("Saved LaTeX file", path=str(output_path))

        # Try to compile (optional validation)
        success, error = LaTeXValidator.validate_compilation(latex)
        if not success:
            logger.warning(
                "LaTeX compilation had issues",
                error=error,
                advice="You may need to fix some syntax manually.",
            )


class BatchConverter:
    """
    Batch processing for multiple PDF documents.
    """

    def __init__(
        self,
        config: Optional[ConversionConfig] = None,
        max_workers: int = 4,
    ):
        """
        Initialize batch converter.

        Args:
            config: Conversion configuration
            max_workers: Maximum parallel workers
        """
        self.config = config or ConversionConfig()
        self.max_workers = max_workers

    def convert_batch(
        self,
        pdf_paths: List[str],
        output_dir: str,
    ) -> dict:
        """
        Convert multiple PDFs in parallel.

        Args:
            pdf_paths: List of PDF file paths
            output_dir: Directory to save output files

        Returns:
            Dictionary mapping input paths to results or errors
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        def process_one(pdf_path: str) -> Tuple[str, Union[str, Exception]]:
            try:
                agent = PDFToLaTeXAgent(self.config)
                filename = Path(pdf_path).stem + ".tex"
                output_path = output_dir / filename
                latex = agent.convert(pdf_path, str(output_path))
                return pdf_path, latex
            except Exception as e:
                return pdf_path, e

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(process_one, path): path for path in pdf_paths
            }

            for future in as_completed(futures):
                path, result = future.result()
                if isinstance(result, Exception):
                    results[path] = f"ERROR: {result}"
                    logger.error("Batch conversion failed", path=path, error=str(result))
                else:
                    results[path] = "SUCCESS"
                    logger.info("Batch conversion completed", path=path)

        return results

