"""
Tests for specialized extraction agents.
"""

from unittest.mock import MagicMock

import pytest
from PIL import Image

from app.converter.extractors import (
    CodeExtractionAgent,
    EquationExtractionAgent,
    FigureExtractionAgent,
    TableExtractionAgent,
)


class TestEquationExtractionAgent:
    """Tests for EquationExtractionAgent."""

    @pytest.fixture
    def agent(self, mock_ocr_client):
        return EquationExtractionAgent(mock_ocr_client)

    def test_extract_single_equation(self, agent, sample_image, mock_ocr_client):
        """Test extracting a single equation."""
        mock_ocr_client.ocr_image.return_value = "$E = mc^2$"

        equations = agent.extract_equations(sample_image)

        assert len(equations) >= 1
        assert "E = mc^2" in equations[0]

    def test_extract_multiline_equation(self, agent, sample_image, mock_ocr_client):
        """Test extracting multi-line equations."""
        mock_ocr_client.ocr_image.return_value = """\\begin{align}
x &= y + z \\\\
a &= b + c
\\end{align}"""

        equations = agent.extract_equations(sample_image)

        assert len(equations) >= 1
        assert "\\begin{align}" in equations[0]

    def test_validate_equation_balances_braces(self, agent):
        """Test that validation balances braces."""
        unbalanced = "\\frac{a}{b"
        result = agent._validate_equation(unbalanced)

        assert result.count("{") == result.count("}")

    def test_estimate_confidence(self, agent):
        """Test confidence estimation."""
        good_eq = "$x = 1$"
        bad_eq = "???"

        good_conf = agent._estimate_confidence(good_eq)
        bad_conf = agent._estimate_confidence(bad_eq)

        assert good_conf > bad_conf


class TestTableExtractionAgent:
    """Tests for TableExtractionAgent."""

    @pytest.fixture
    def agent(self, mock_ocr_client):
        return TableExtractionAgent(mock_ocr_client)

    def test_extract_simple_table(self, agent, sample_image, mock_ocr_client):
        """Test extracting a simple table."""
        mock_ocr_client.ocr_image.return_value = """\\begin{table}[h]
\\centering
\\begin{tabular}{lc}
\\toprule
Name & Value \\\\
\\midrule
A & 1 \\\\
\\bottomrule
\\end{tabular}
\\end{table}"""

        table = agent.extract_table(sample_image)

        assert "\\begin{table}" in table
        assert "\\begin{tabular}" in table
        assert "\\toprule" in table

    def test_validate_adds_table_wrapper(self, agent):
        """Test that validation adds table environment if missing."""
        tabular_only = """\\begin{tabular}{lc}
A & B \\\\
\\end{tabular}"""

        result = agent._validate_table(tabular_only)

        assert "\\begin{table}" in result
        assert "\\end{table}" in result


class TestFigureExtractionAgent:
    """Tests for FigureExtractionAgent."""

    @pytest.fixture
    def agent(self, mock_ocr_client):
        return FigureExtractionAgent(mock_ocr_client)

    def test_generate_caption(self, agent, sample_image, mock_ocr_client):
        """Test caption generation."""
        mock_ocr_client.ocr_image.return_value = "Graph showing linear relationship between variables."

        caption = agent.generate_caption(sample_image)

        assert len(caption) > 0
        assert "Graph" in caption or "graph" in caption

    def test_generate_latex_figure(self, agent, mock_ocr_client, temp_dir):
        """Test LaTeX figure environment generation."""
        # Create a test image
        img = Image.new("RGB", (100, 100), color="white")
        img_path = temp_dir / "test_fig.png"
        img.save(img_path)

        mock_ocr_client.ocr_image.return_value = "Test caption."

        latex = agent.generate_latex_figure(
            str(img_path),
            caption="Test caption",
            label="fig:test",
        )

        assert "\\begin{figure}" in latex
        assert "\\includegraphics" in latex
        assert "\\caption{Test caption}" in latex
        assert "\\label{fig:test}" in latex


class TestCodeExtractionAgent:
    """Tests for CodeExtractionAgent."""

    @pytest.fixture
    def agent(self, mock_ocr_client):
        return CodeExtractionAgent(mock_ocr_client)

    def test_extract_code_block(self, agent, sample_image, mock_ocr_client):
        """Test extracting a code block."""
        mock_ocr_client.ocr_image.return_value = """\\begin{lstlisting}[language=Python]
def hello():
    print("Hello, World!")
\\end{lstlisting}"""

        code = agent.extract_code(sample_image)

        assert "\\begin{lstlisting}" in code
        assert "def hello" in code

