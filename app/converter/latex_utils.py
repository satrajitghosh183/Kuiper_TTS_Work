"""
LaTeX utilities for cleaning, validation, and document generation.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import structlog

from app.exceptions import LaTeXValidationError

logger = structlog.get_logger()


class LaTeXCleaner:
    """
    Cleans and fixes common LaTeX issues in generated content.
    """

    # Patterns for cleaning
    MARKDOWN_CODE_BLOCK = re.compile(r"```(?:latex|tex)?\n?", re.IGNORECASE)
    DOUBLE_NEWLINES = re.compile(r"\n{3,}")
    MULTIPLE_SPACES = re.compile(r"  +")

    # Common escape issues
    ESCAPE_FIXES = [
        (r"\\\\n", "\n"),
        (r"\\n", "\n"),
        (r"\\_", "_"),  # Sometimes over-escaped
    ]

    # Environment spacing
    ENV_END_PATTERN = re.compile(r"(\\end\{[^}]+\})(\s*)(\\begin\{[^}]+\})")

    @classmethod
    def clean(cls, latex: str) -> str:
        """
        Clean and fix common LaTeX issues.

        Args:
            latex: Raw LaTeX content

        Returns:
            Cleaned LaTeX content
        """
        # Remove markdown code blocks if present
        latex = cls.MARKDOWN_CODE_BLOCK.sub("", latex)
        latex = latex.replace("```", "")

        # Fix escape issues
        for pattern, replacement in cls.ESCAPE_FIXES:
            latex = latex.replace(pattern, replacement)

        # Ensure proper spacing around environments
        latex = cls.ENV_END_PATTERN.sub(r"\1\n\n\3", latex)

        # Remove excessive newlines
        latex = cls.DOUBLE_NEWLINES.sub("\n\n", latex)

        # Strip leading/trailing whitespace
        latex = latex.strip()

        return latex

    @classmethod
    def fix_braces(cls, latex: str) -> str:
        """
        Balance unmatched braces in LaTeX content.

        Args:
            latex: LaTeX content

        Returns:
            LaTeX with balanced braces
        """
        open_count = latex.count("{")
        close_count = latex.count("}")

        if open_count > close_count:
            latex += "}" * (open_count - close_count)
        elif close_count > open_count:
            latex = "{" * (close_count - open_count) + latex

        return latex

    @classmethod
    def fix_environments(cls, latex: str) -> str:
        """
        Fix unclosed or mismatched environments.

        Args:
            latex: LaTeX content

        Returns:
            LaTeX with fixed environments
        """
        # Find all \begin{...} and \end{...}
        begin_pattern = re.compile(r"\\begin\{([^}]+)\}")
        end_pattern = re.compile(r"\\end\{([^}]+)\}")

        begins = [(m.group(1), m.start()) for m in begin_pattern.finditer(latex)]
        ends = [(m.group(1), m.start()) for m in end_pattern.finditer(latex)]

        # Track opened environments
        stack = []
        for env, pos in sorted(begins + [(f"END:{e}", p) for e, p in ends], key=lambda x: x[1]):
            if env.startswith("END:"):
                actual_env = env[4:]
                if stack and stack[-1] == actual_env:
                    stack.pop()
            else:
                stack.append(env)

        # Close any unclosed environments in reverse order
        for env in reversed(stack):
            latex += f"\n\\end{{{env}}}"
            logger.warning(f"Auto-closed unclosed environment: {env}")

        return latex

    @classmethod
    def escape_special_chars(cls, text: str) -> str:
        """
        Escape LaTeX special characters in plain text.

        Args:
            text: Plain text to escape

        Returns:
            Escaped text safe for LaTeX
        """
        special_chars = {
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "~": r"\textasciitilde{}",
            "^": r"\textasciicircum{}",
            "\\": r"\textbackslash{}",
        }

        for char, escape in special_chars.items():
            # Don't escape if already escaped
            text = re.sub(rf"(?<!\\){re.escape(char)}", escape, text)

        return text


class LaTeXValidator:
    """
    Validates LaTeX content for syntax errors and compilability.
    """

    # Required commands for a valid document
    REQUIRED_STRUCTURE = [
        r"\\documentclass",
        r"\\begin\{document\}",
        r"\\end\{document\}",
    ]

    @classmethod
    def validate_syntax(cls, latex: str) -> Tuple[bool, List[str]]:
        """
        Perform basic syntax validation on LaTeX content.

        Args:
            latex: LaTeX content to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check brace balance
        if latex.count("{") != latex.count("}"):
            errors.append(
                f"Unbalanced braces: {latex.count('{')} open, {latex.count('}')} close"
            )

        # Check environment balance
        begin_count = len(re.findall(r"\\begin\{", latex))
        end_count = len(re.findall(r"\\end\{", latex))
        if begin_count != end_count:
            errors.append(
                f"Unbalanced environments: {begin_count} begins, {end_count} ends"
            )

        # Check for common errors
        if re.search(r"\$\$\$", latex):
            errors.append("Triple dollar signs found (invalid math mode)")

        if re.search(r"\\\\\\\\", latex):
            errors.append("Quadruple backslash found (likely escape error)")

        return len(errors) == 0, errors

    @classmethod
    def validate_compilation(
        cls, latex: str, timeout: int = 60
    ) -> Tuple[bool, Optional[str]]:
        """
        Attempt to compile LaTeX and check for errors.

        Args:
            latex: Complete LaTeX document
            timeout: Compilation timeout in seconds

        Returns:
            Tuple of (compiled_successfully, error_message)
        """
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tex_path = Path(tmpdir) / "test.tex"
                tex_path.write_text(latex, encoding="utf-8")

                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", str(tex_path)],
                    cwd=tmpdir,
                    capture_output=True,
                    timeout=timeout,
                    text=True,
                )

                if result.returncode == 0:
                    return True, None

                # Extract error from log
                log_path = Path(tmpdir) / "test.log"
                if log_path.exists():
                    log_content = log_path.read_text()
                    # Find first error
                    error_match = re.search(r"^!(.*?)$", log_content, re.MULTILINE)
                    if error_match:
                        return False, error_match.group(1).strip()

                return False, "Compilation failed (see log for details)"

        except FileNotFoundError:
            logger.warning("pdflatex not found - skipping compilation validation")
            return True, None  # Can't validate, assume OK
        except subprocess.TimeoutExpired:
            return False, "Compilation timed out"
        except Exception as e:
            return False, str(e)


class LaTeXDocumentGenerator:
    """
    Generates complete LaTeX documents with proper preamble.
    """

    DEFAULT_PACKAGES = [
        "amsmath",
        "amssymb",
        "amsfonts",
        "graphicx",
        "hyperref",
        "geometry",
        "booktabs",
        "longtable",
        "xcolor",
        "float",
        "enumitem",
    ]

    @classmethod
    def generate_preamble(
        cls,
        document_class: str = "article",
        packages: Optional[List[str]] = None,
        graphics_path: Optional[str] = None,
        custom_commands: Optional[List[str]] = None,
        geometry: str = "margin=1in",
    ) -> str:
        """
        Generate LaTeX preamble.

        Args:
            document_class: LaTeX document class
            packages: List of packages to include
            graphics_path: Path to graphics directory
            custom_commands: Additional preamble commands
            geometry: Geometry package options

        Returns:
            Preamble string
        """
        packages = packages or cls.DEFAULT_PACKAGES

        lines = [f"\\documentclass[12pt]{{{document_class}}}", "", "% Packages"]

        for pkg in packages:
            if pkg == "geometry" and geometry:
                lines.append(f"\\usepackage[{geometry}]{{{pkg}}}")
            elif pkg == "hyperref":
                lines.append(
                    f"\\usepackage[colorlinks=true,linkcolor=blue,urlcolor=blue]{{{pkg}}}"
                )
            else:
                lines.append(f"\\usepackage{{{pkg}}}")

        if graphics_path:
            lines.extend(["", f"% Graphics path", f"\\graphicspath{{{{{graphics_path}/}}}}"])

        lines.extend(
            [
                "",
                "% Document settings",
                "\\setlength{\\parindent}{0pt}",
                "\\setlength{\\parskip}{1em}",
            ]
        )

        if custom_commands:
            lines.extend(["", "% Custom commands"])
            lines.extend(custom_commands)

        return "\n".join(lines)

    @classmethod
    def generate_document(
        cls,
        body: str,
        document_class: str = "article",
        packages: Optional[List[str]] = None,
        graphics_path: Optional[str] = None,
        title: Optional[str] = None,
        author: Optional[str] = None,
        date: Optional[str] = None,
    ) -> str:
        """
        Generate a complete LaTeX document.

        Args:
            body: Document body content
            document_class: LaTeX document class
            packages: List of packages to include
            graphics_path: Path to graphics directory
            title: Document title
            author: Document author
            date: Document date

        Returns:
            Complete LaTeX document
        """
        preamble = cls.generate_preamble(
            document_class=document_class,
            packages=packages,
            graphics_path=graphics_path,
        )

        title_block = ""
        if title or author:
            if title:
                title_block += f"\\title{{{title}}}\n"
            if author:
                title_block += f"\\author{{{author}}}\n"
            if date:
                title_block += f"\\date{{{date}}}\n"
            else:
                title_block += "\\date{\\today}\n"

        maketitle = "\\maketitle\n\n" if title_block else ""

        document = f"""{preamble}

{title_block}
\\begin{{document}}

{maketitle}{body}

\\end{{document}}
"""
        return document

