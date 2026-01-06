"""
Specialized extraction agents for equations, tables, and figures.
"""

from __future__ import annotations

import re
from typing import List, Optional

import structlog
from PIL import Image

from app.models import ExtractionResult
from app.ocr.base import BaseOCRClient
from app.ocr.prompts import (
    CODE_EXTRACTION_PROMPT,
    EQUATION_EXTRACTION_PROMPT,
    FIGURE_CAPTION_PROMPT,
    TABLE_EXTRACTION_PROMPT,
)

logger = structlog.get_logger()


class EquationExtractionAgent:
    """
    Specialized agent for extracting and converting mathematical equations.

    Uses targeted prompts and post-processing for high-accuracy math OCR.
    Focuses on producing clean, compilable LaTeX equations.

    Example:
        >>> client = HuggingFaceOCRClient()
        >>> agent = EquationExtractionAgent(client)
        >>> equations = agent.extract_equations(image)
        >>> for eq in equations:
        ...     print(eq)
    """

    def __init__(self, client: BaseOCRClient):
        """
        Initialize the equation extraction agent.

        Args:
            client: OCR client to use for extraction
        """
        self.client = client

    def extract_equations(self, image: Image.Image) -> List[str]:
        """
        Extract all equations from an image.

        Args:
            image: PIL Image object

        Returns:
            List of LaTeX equation strings
        """
        raw_output = self.client.ocr_image(
            image, prompt=EQUATION_EXTRACTION_PROMPT
        )

        # Parse and clean equations
        equations = self._parse_equations(raw_output)
        return [self._validate_equation(eq) for eq in equations if eq.strip()]

    def extract_with_context(
        self, image: Image.Image, page_num: int
    ) -> List[ExtractionResult]:
        """
        Extract equations with metadata.

        Args:
            image: PIL Image object
            page_num: Source page number

        Returns:
            List of ExtractionResult objects
        """
        equations = self.extract_equations(image)
        results = []

        for i, eq in enumerate(equations):
            results.append(
                ExtractionResult(
                    content=eq,
                    confidence=self._estimate_confidence(eq),
                    source_page=page_num,
                )
            )

        return results

    def _parse_equations(self, raw: str) -> List[str]:
        """
        Parse raw output into individual equations.

        Args:
            raw: Raw OCR output

        Returns:
            List of equation strings
        """
        # Remove any markdown formatting
        raw = re.sub(r"```(?:latex)?", "", raw)
        raw = raw.replace("```", "")

        lines = raw.strip().split("\n")
        equations = []

        current_eq = []
        in_multiline = False

        for line in lines:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#") or line.startswith("//"):
                if current_eq:
                    equations.append("\n".join(current_eq))
                    current_eq = []
                continue

            # Detect multi-line environments
            if re.match(r"\\begin\{(align|equation|gather|cases)", line):
                in_multiline = True

            current_eq.append(line)

            if re.match(r"\\end\{(align|equation|gather|cases)", line):
                in_multiline = False
                equations.append("\n".join(current_eq))
                current_eq = []
            elif not in_multiline:
                equations.append("\n".join(current_eq))
                current_eq = []

        if current_eq:
            equations.append("\n".join(current_eq))

        return equations

    def _validate_equation(self, equation: str) -> str:
        """
        Validate and fix common equation issues.

        Args:
            equation: LaTeX equation string

        Returns:
            Fixed equation string
        """
        # Balance braces
        open_count = equation.count("{")
        close_count = equation.count("}")

        if open_count > close_count:
            equation += "}" * (open_count - close_count)
        elif close_count > open_count:
            equation = "{" * (close_count - open_count) + equation

        # Balance dollar signs for inline math
        if equation.startswith("$") and not equation.startswith("$$"):
            if equation.count("$") % 2 != 0:
                equation += "$"

        # Balance display math
        if equation.startswith("$$"):
            if equation.count("$$") % 2 != 0:
                equation += "$$"

        return equation

    def _estimate_confidence(self, equation: str) -> float:
        """
        Estimate confidence score for an equation.

        Args:
            equation: LaTeX equation string

        Returns:
            Confidence score between 0 and 1
        """
        score = 1.0

        # Penalize unbalanced braces
        if equation.count("{") != equation.count("}"):
            score -= 0.2

        # Penalize very short equations (might be fragments)
        if len(equation) < 5:
            score -= 0.1

        # Penalize suspicious patterns
        if "???" in equation or "..." in equation:
            score -= 0.3

        return max(0.0, min(1.0, score))


class TableExtractionAgent:
    """
    Specialized agent for extracting and converting tables.

    Produces clean LaTeX tabular environments with proper formatting.
    Supports booktabs styling and various table layouts.

    Example:
        >>> client = HuggingFaceOCRClient()
        >>> agent = TableExtractionAgent(client)
        >>> table_latex = agent.extract_table(image)
    """

    def __init__(self, client: BaseOCRClient):
        """
        Initialize the table extraction agent.

        Args:
            client: OCR client to use for extraction
        """
        self.client = client

    def extract_table(self, image: Image.Image) -> str:
        """
        Extract table from image as LaTeX.

        Args:
            image: PIL Image object

        Returns:
            LaTeX table code
        """
        raw_output = self.client.ocr_image(image, prompt=TABLE_EXTRACTION_PROMPT)

        # Clean and validate
        table = self._clean_table(raw_output)
        table = self._validate_table(table)

        return table

    def extract_with_context(
        self, image: Image.Image, page_num: int
    ) -> ExtractionResult:
        """
        Extract table with metadata.

        Args:
            image: PIL Image object
            page_num: Source page number

        Returns:
            ExtractionResult object
        """
        table = self.extract_table(image)

        return ExtractionResult(
            content=table,
            confidence=self._estimate_confidence(table),
            source_page=page_num,
        )

    def _clean_table(self, raw: str) -> str:
        """
        Clean raw table output.

        Args:
            raw: Raw OCR output

        Returns:
            Cleaned table string
        """
        # Remove markdown formatting
        raw = re.sub(r"```(?:latex)?", "", raw)
        raw = raw.replace("```", "")

        return raw.strip()

    def _validate_table(self, table: str) -> str:
        """
        Validate and fix table structure.

        Args:
            table: LaTeX table code

        Returns:
            Fixed table code
        """
        # Ensure proper environment structure
        if "\\begin{table}" not in table and "\\begin{tabular}" in table:
            # Wrap tabular in table environment
            table = f"""\\begin{{table}}[h]
\\centering
{table}
\\end{{table}}"""

        # Check for booktabs commands
        if "\\begin{tabular}" in table:
            # Add booktabs if not present
            if "\\toprule" not in table and "\\hline" in table:
                table = table.replace("\\hline", "\\midrule", 1)
                # First hline -> toprule
                table = re.sub(r"(\\begin\{tabular\}[^}]*\})\s*\\midrule",
                              r"\1\n\\toprule", table, count=1)
                # Last hline -> bottomrule
                table = re.sub(r"\\midrule(\s*\\end\{tabular\})",
                              r"\\bottomrule\1", table)

        return table

    def _estimate_confidence(self, table: str) -> float:
        """
        Estimate confidence score for a table.

        Args:
            table: LaTeX table code

        Returns:
            Confidence score between 0 and 1
        """
        score = 1.0

        # Check for required elements
        if "\\begin{tabular}" not in table:
            score -= 0.5

        # Check for proper row endings
        if table.count("\\\\") < 2:
            score -= 0.2

        # Check for column separators
        if "&" not in table:
            score -= 0.3

        return max(0.0, min(1.0, score))


class FigureExtractionAgent:
    """
    Agent for extracting figures and generating captions.
    """

    def __init__(self, client: BaseOCRClient):
        """
        Initialize the figure extraction agent.

        Args:
            client: OCR client to use for caption generation
        """
        self.client = client

    def generate_caption(self, image: Image.Image) -> str:
        """
        Generate a caption for a figure.

        Args:
            image: PIL Image of the figure

        Returns:
            Caption text
        """
        caption = self.client.ocr_image(
            image, prompt=FIGURE_CAPTION_PROMPT, output_format="plain"
        )

        # Clean caption
        caption = caption.strip()

        # Remove common prefixes
        prefixes_to_remove = [
            "This figure shows ",
            "The figure depicts ",
            "This image shows ",
            "The image depicts ",
            "Caption: ",
        ]
        for prefix in prefixes_to_remove:
            if caption.lower().startswith(prefix.lower()):
                caption = caption[len(prefix):]

        # Capitalize first letter
        if caption:
            caption = caption[0].upper() + caption[1:]

        return caption

    def generate_latex_figure(
        self,
        image_path: str,
        caption: Optional[str] = None,
        label: Optional[str] = None,
        width: str = "0.8\\textwidth",
        position: str = "h",
    ) -> str:
        """
        Generate LaTeX figure environment.

        Args:
            image_path: Path to image file
            caption: Figure caption (generated if None)
            label: Figure label
            width: Width specification
            position: Float position (h, t, b, p)

        Returns:
            LaTeX figure code
        """
        if caption is None:
            try:
                img = Image.open(image_path)
                caption = self.generate_caption(img)
            except Exception:
                caption = "Figure description."

        if label is None:
            # Generate label from filename
            import os
            basename = os.path.splitext(os.path.basename(image_path))[0]
            label = f"fig:{basename}"

        return f"""\\begin{{figure}}[{position}]
\\centering
\\includegraphics[width={width}]{{{image_path}}}
\\caption{{{caption}}}
\\label{{{label}}}
\\end{{figure}}"""


class CodeExtractionAgent:
    """
    Agent for extracting code blocks from documents.
    """

    def __init__(self, client: BaseOCRClient):
        """
        Initialize the code extraction agent.

        Args:
            client: OCR client to use for extraction
        """
        self.client = client

    def extract_code(self, image: Image.Image) -> str:
        """
        Extract code blocks from an image.

        Args:
            image: PIL Image object

        Returns:
            LaTeX lstlisting code
        """
        raw_output = self.client.ocr_image(
            image, prompt=CODE_EXTRACTION_PROMPT
        )

        return self._clean_code(raw_output)

    def _clean_code(self, raw: str) -> str:
        """
        Clean raw code output.

        Args:
            raw: Raw OCR output

        Returns:
            Cleaned code string
        """
        # Remove markdown formatting but preserve lstlisting
        raw = re.sub(r"```(?!lstlisting)", "", raw)

        return raw.strip()

