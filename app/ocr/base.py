"""
Base OCR client interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from PIL import Image


class BaseOCRClient(ABC):
    """
    Abstract base class for OCR clients.
    
    All OCR implementations must inherit from this class and implement
    the required methods.
    """

    @abstractmethod
    def ocr_image(
        self,
        image: Image.Image,
        prompt: Optional[str] = None,
        output_format: str = "latex",
    ) -> str:
        """
        Perform OCR on an image and return structured output.

        Args:
            image: PIL Image object
            prompt: Custom prompt (uses default if None)
            output_format: "latex", "markdown", or "plain"

        Returns:
            Extracted text in specified format
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the OCR client is available and properly configured.

        Returns:
            True if client is ready to use
        """
        pass

    def get_default_prompt(self, output_format: str) -> str:
        """
        Get default prompt based on output format.

        Args:
            output_format: One of "latex", "markdown", or "plain"

        Returns:
            Default prompt string
        """
        prompts = {
            "latex": """Convert this document page to LaTeX source code.

REQUIREMENTS:
1. Use proper LaTeX syntax and environments
2. Convert equations to LaTeX math mode ($ for inline, $$ or equation environment for display)
3. Preserve document structure (sections, subsections, paragraphs)
4. Convert tables to tabular/longtable environments
5. Mark figure locations with \\includegraphics{} placeholders
6. Use appropriate packages (amsmath, amssymb for math; booktabs for tables)
7. Preserve formatting (bold, italic, underline) using \\textbf{}, \\textit{}, \\underline{}

OUTPUT: Return ONLY the LaTeX code, no explanations or markdown wrappers.""",
            "markdown": """Extract all text from this document maintaining structure.
Return as markdown with:
- Headers using # syntax
- Tables using | syntax  
- Math equations in $...$ or $$...$$ 
- Preserve lists and formatting""",
            "plain": """Extract all text from this document.
Read naturally as if transcribing.
Maintain paragraph breaks.
Describe any images or figures briefly.""",
        }
        return prompts.get(output_format, prompts["latex"])

