"""
Tests for LaTeX utilities.
"""

import pytest

from app.converter.latex_utils import (
    LaTeXCleaner,
    LaTeXDocumentGenerator,
    LaTeXValidator,
)


class TestLaTeXCleaner:
    """Tests for LaTeXCleaner class."""

    def test_clean_markdown_blocks(self):
        """Test removal of markdown code blocks."""
        input_text = "```latex\n\\section{Test}\n```"
        result = LaTeXCleaner.clean(input_text)

        assert "```" not in result
        assert "\\section{Test}" in result

    def test_clean_double_newlines(self):
        """Test excessive newline removal."""
        input_text = "First paragraph\n\n\n\n\nSecond paragraph"
        result = LaTeXCleaner.clean(input_text)

        assert "\n\n\n" not in result

    def test_fix_braces_unbalanced_open(self):
        """Test fixing unbalanced opening braces."""
        input_text = "\\textbf{bold text"
        result = LaTeXCleaner.fix_braces(input_text)

        assert result.count("{") == result.count("}")

    def test_fix_braces_unbalanced_close(self):
        """Test fixing unbalanced closing braces."""
        input_text = "bold text}"
        result = LaTeXCleaner.fix_braces(input_text)

        assert result.count("{") == result.count("}")

    def test_fix_braces_balanced(self):
        """Test that balanced braces are unchanged."""
        input_text = "\\textbf{bold} and \\textit{italic}"
        result = LaTeXCleaner.fix_braces(input_text)

        assert result == input_text

    def test_escape_special_chars(self):
        """Test escaping special LaTeX characters."""
        input_text = "100% discount & free #1"
        result = LaTeXCleaner.escape_special_chars(input_text)

        assert "\\%" in result
        assert "\\&" in result
        assert "\\#" in result


class TestLaTeXValidator:
    """Tests for LaTeXValidator class."""

    def test_validate_syntax_balanced(self):
        """Test syntax validation with balanced content."""
        latex = """\\documentclass{article}
\\begin{document}
\\section{Test}
Content here.
\\end{document}"""

        is_valid, errors = LaTeXValidator.validate_syntax(latex)
        assert is_valid
        assert len(errors) == 0

    def test_validate_syntax_unbalanced_braces(self):
        """Test syntax validation with unbalanced braces."""
        latex = "\\textbf{unbalanced"

        is_valid, errors = LaTeXValidator.validate_syntax(latex)
        assert not is_valid
        assert any("brace" in e.lower() for e in errors)

    def test_validate_syntax_unbalanced_environments(self):
        """Test syntax validation with unbalanced environments."""
        latex = "\\begin{equation} x = 1"

        is_valid, errors = LaTeXValidator.validate_syntax(latex)
        assert not is_valid
        assert any("environment" in e.lower() for e in errors)


class TestLaTeXDocumentGenerator:
    """Tests for LaTeXDocumentGenerator class."""

    def test_generate_preamble_default(self):
        """Test default preamble generation."""
        preamble = LaTeXDocumentGenerator.generate_preamble()

        assert "\\documentclass" in preamble
        assert "\\usepackage{amsmath}" in preamble
        assert "\\usepackage{graphicx}" in preamble

    def test_generate_preamble_custom_class(self):
        """Test preamble with custom document class."""
        preamble = LaTeXDocumentGenerator.generate_preamble(
            document_class="report"
        )

        assert "\\documentclass[12pt]{report}" in preamble

    def test_generate_preamble_with_graphics_path(self):
        """Test preamble with graphics path."""
        preamble = LaTeXDocumentGenerator.generate_preamble(
            graphics_path="./figures"
        )

        assert "\\graphicspath" in preamble
        assert "figures" in preamble

    def test_generate_document_complete(self):
        """Test complete document generation."""
        body = "\\section{Test}\nContent here."

        doc = LaTeXDocumentGenerator.generate_document(
            body=body,
            title="Test Document",
            author="Test Author",
        )

        assert "\\documentclass" in doc
        assert "\\begin{document}" in doc
        assert "\\end{document}" in doc
        assert "\\title{Test Document}" in doc
        assert "\\author{Test Author}" in doc
        assert "\\maketitle" in doc
        assert body in doc

