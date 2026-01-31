"""
PDF-to-LaTeX Statistical Validator.

A comprehensive statistical comparison tool that identifies exactly what content
from the PDF is present or missing in the LaTeX conversion.

Features:
- Precise element counting (equations, tables, figures, sections)
- Location-based missing content identification
- Statistical coverage analysis
- Per-page breakdown with specific missing items
- No grades or scores - pure statistical comparison
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import structlog

logger = structlog.get_logger()


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class EquationInfo:
    """Information about a detected equation."""
    page: int
    equation_number: Optional[str]  # e.g., "(1)", "(2.3)"
    content_preview: str  # First ~50 chars
    equation_type: str  # "inline", "display", "numbered"
    found_in_latex: bool = False


@dataclass
class TableInfo:
    """Information about a detected table."""
    page: int
    table_number: Optional[str]  # e.g., "Table 1", "TABLE I"
    caption_preview: str
    estimated_rows: int
    estimated_cols: int
    found_in_latex: bool = False


@dataclass
class FigureInfo:
    """Information about a detected figure."""
    page: int
    figure_number: Optional[str]  # e.g., "Fig. 1", "Figure 2"
    caption_preview: str
    found_in_latex: bool = False


@dataclass
class SectionInfo:
    """Information about a detected section."""
    page: int
    section_number: Optional[str]  # e.g., "1.", "2.1"
    title: str
    level: int  # 1=section, 2=subsection, 3=subsubsection
    found_in_latex: bool = False


@dataclass
class PageComparison:
    """Statistical comparison for a single page."""
    page_number: int
    
    # Word statistics
    pdf_words: int = 0
    latex_words: int = 0
    word_difference: int = 0
    word_coverage_pct: float = 0.0
    
    # Character statistics
    pdf_chars: int = 0
    latex_chars: int = 0
    char_difference: int = 0
    char_coverage_pct: float = 0.0
    
    # Element counts for this page
    pdf_equations: int = 0
    latex_equations: int = 0
    pdf_tables: int = 0
    latex_tables: int = 0
    pdf_figures: int = 0
    latex_figures: int = 0
    
    # Missing content indicators
    missing_equations: int = 0
    missing_content_keywords: List[str] = field(default_factory=list)
    
    # Text similarity
    similarity_pct: float = 0.0
    
    # Status
    status: str = "OK"  # "OK", "PARTIAL", "LOW_COVERAGE", "MISSING"


@dataclass
class ContentStatistics:
    """Overall content statistics comparison."""
    
    # Document-level counts
    pdf_total_pages: int = 0
    latex_total_lines: int = 0
    
    # Word statistics
    pdf_total_words: int = 0
    latex_total_words: int = 0
    word_difference: int = 0
    word_coverage_pct: float = 0.0
    
    # Character statistics  
    pdf_total_chars: int = 0
    latex_total_chars: int = 0
    char_difference: int = 0
    char_coverage_pct: float = 0.0
    
    # Equation statistics
    pdf_equations_estimated: int = 0
    pdf_numbered_equations: int = 0
    pdf_inline_math_indicators: int = 0
    latex_inline_equations: int = 0
    latex_display_equations: int = 0
    latex_equation_environments: int = 0
    latex_total_equations: int = 0
    equation_difference: int = 0
    
    # Table statistics
    pdf_tables_detected: int = 0
    pdf_table_references: List[str] = field(default_factory=list)
    latex_tables: int = 0
    latex_tabular_environments: int = 0
    table_difference: int = 0
    missing_tables: List[str] = field(default_factory=list)
    
    # Figure statistics
    pdf_figures_detected: int = 0
    pdf_figure_references: List[str] = field(default_factory=list)
    latex_figures: int = 0
    latex_includegraphics: int = 0
    figure_difference: int = 0
    missing_figures: List[str] = field(default_factory=list)
    
    # Section statistics
    pdf_sections_estimated: int = 0
    pdf_section_titles: List[str] = field(default_factory=list)
    latex_sections: int = 0
    latex_subsections: int = 0
    latex_subsubsections: int = 0
    latex_total_sections: int = 0
    section_difference: int = 0
    missing_sections: List[str] = field(default_factory=list)
    
    # List statistics
    latex_itemize_lists: int = 0
    latex_enumerate_lists: int = 0
    latex_total_list_items: int = 0
    
    # Reference statistics
    latex_labels: int = 0
    latex_refs: int = 0
    latex_citations: int = 0
    latex_footnotes: int = 0
    
    # Math element statistics
    latex_greek_letters: int = 0
    latex_fractions: int = 0
    latex_integrals: int = 0
    latex_summations: int = 0
    latex_subscripts: int = 0
    latex_superscripts: int = 0


@dataclass
class LatexSyntaxCheck:
    """LaTeX syntax validation results."""
    
    is_valid: bool = True
    has_document_class: bool = False
    has_begin_document: bool = False
    has_end_document: bool = False
    
    # Balance checks
    open_braces: int = 0
    close_braces: int = 0
    braces_balanced: bool = True
    brace_difference: int = 0
    
    begin_environments: int = 0
    end_environments: int = 0
    environments_balanced: bool = True
    unbalanced_environments: List[str] = field(default_factory=list)
    
    # Math delimiters
    inline_math_delimiters: int = 0
    math_balanced: bool = True
    
    # Issues found
    syntax_issues: List[str] = field(default_factory=list)
    
    # Packages
    packages_used: List[str] = field(default_factory=list)


@dataclass
class VocabularyComparison:
    """Vocabulary statistics."""
    
    pdf_unique_words: int = 0
    latex_unique_words: int = 0
    shared_words: int = 0
    words_only_in_pdf: int = 0
    words_only_in_latex: int = 0
    vocabulary_overlap_pct: float = 0.0
    
    # Key terms analysis
    top_pdf_terms: List[Tuple[str, int]] = field(default_factory=list)
    top_latex_terms: List[Tuple[str, int]] = field(default_factory=list)
    missing_key_terms: List[str] = field(default_factory=list)
    
    # Numbers
    pdf_numbers: int = 0
    latex_numbers: int = 0
    numbers_matched_pct: float = 0.0
    
    # Technical terms
    pdf_technical_terms: int = 0
    latex_technical_terms: int = 0
    technical_terms_matched_pct: float = 0.0


@dataclass
class ValidationReport:
    """Complete statistical validation report."""
    
    # Meta
    pdf_path: str
    latex_path: str
    validation_time: str = ""
    
    # Main statistics
    statistics: ContentStatistics = field(default_factory=ContentStatistics)
    
    # LaTeX syntax check
    latex_syntax: LatexSyntaxCheck = field(default_factory=LatexSyntaxCheck)
    
    # Vocabulary comparison
    vocabulary: VocabularyComparison = field(default_factory=VocabularyComparison)
    
    # Per-page comparison
    page_comparisons: List[PageComparison] = field(default_factory=list)
    
    # Missing content tracking
    equations_in_pdf: List[EquationInfo] = field(default_factory=list)
    tables_in_pdf: List[TableInfo] = field(default_factory=list)
    figures_in_pdf: List[FigureInfo] = field(default_factory=list)
    sections_in_pdf: List[SectionInfo] = field(default_factory=list)
    
    # Summary
    pages_with_issues: List[int] = field(default_factory=list)
    critical_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.validation_time:
            self.validation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return {
            "meta": {
                "pdf_path": self.pdf_path,
                "latex_path": self.latex_path,
                "validation_time": self.validation_time,
            },
            "pdf": {
                "pages": self.statistics.pdf_total_pages,
                "words": self.statistics.pdf_total_words,
                "characters": self.statistics.pdf_total_chars,
            },
            "latex": {
                "lines_of_code": self.statistics.latex_total_lines,
                "words_extracted": self.statistics.latex_total_words,
                "characters_extracted": self.statistics.latex_total_chars,
            },
            "coverage": {
                "word_coverage_pct": round(self.statistics.word_coverage_pct, 1),
                "char_coverage_pct": round(self.statistics.char_coverage_pct, 1),
                "missing_words": self.statistics.word_difference,
                "missing_characters": self.statistics.char_difference,
            },
            "equation_statistics": {
                "pdf_estimated": self.statistics.pdf_equations_estimated,
                "pdf_numbered": self.statistics.pdf_numbered_equations,
                "latex_inline": self.statistics.latex_inline_equations,
                "latex_display": self.statistics.latex_display_equations,
                "latex_environments": self.statistics.latex_equation_environments,
                "latex_total": self.statistics.latex_total_equations,
                "difference": self.statistics.equation_difference,
            },
            "table_statistics": {
                "pdf_detected": self.statistics.pdf_tables_detected,
                "pdf_references": self.statistics.pdf_table_references,
                "latex_tables": self.statistics.latex_tables,
                "latex_tabular": self.statistics.latex_tabular_environments,
                "difference": self.statistics.table_difference,
                "missing": self.statistics.missing_tables,
            },
            "figure_statistics": {
                "pdf_detected": self.statistics.pdf_figures_detected,
                "pdf_references": self.statistics.pdf_figure_references,
                "latex_figures": self.statistics.latex_figures,
                "latex_includegraphics": self.statistics.latex_includegraphics,
                "difference": self.statistics.figure_difference,
                "missing": self.statistics.missing_figures,
            },
            "section_statistics": {
                "pdf_estimated": self.statistics.pdf_sections_estimated,
                "pdf_titles": self.statistics.pdf_section_titles[:10],
                "latex_sections": self.statistics.latex_sections,
                "latex_subsections": self.statistics.latex_subsections,
                "latex_total": self.statistics.latex_total_sections,
                "difference": self.statistics.section_difference,
                "missing": self.statistics.missing_sections[:10],
            },
            "latex_syntax": {
                "valid": self.latex_syntax.is_valid,
                "braces_balanced": self.latex_syntax.braces_balanced,
                "environments_balanced": self.latex_syntax.environments_balanced,
                "unbalanced": self.latex_syntax.unbalanced_environments,
                "packages": self.latex_syntax.packages_used,
                "issues": self.latex_syntax.syntax_issues,
            },
            "vocabulary": {
                "pdf_unique": self.vocabulary.pdf_unique_words,
                "latex_unique": self.vocabulary.latex_unique_words,
                "shared": self.vocabulary.shared_words,
                "overlap_pct": round(self.vocabulary.vocabulary_overlap_pct, 1),
                "missing_key_terms": self.vocabulary.missing_key_terms[:15],
                "numbers_matched_pct": round(self.vocabulary.numbers_matched_pct, 1),
            },
            "page_summary": [
                {
                    "page": p.page_number,
                    "pdf_words": p.pdf_words,
                    "latex_words": p.latex_words,
                    "coverage_pct": round(p.word_coverage_pct, 1),
                    "similarity_pct": round(p.similarity_pct, 1),
                    "status": p.status,
                }
                for p in self.page_comparisons
            ],
            "issues": {
                "pages_with_issues": self.pages_with_issues,
                "critical": self.critical_issues,
                "warnings": self.warnings,
            },
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# ============================================================================
# MAIN VALIDATOR CLASS
# ============================================================================

class ConversionValidator:
    """
    Statistical PDF-to-LaTeX conversion validator.
    
    Provides precise statistical comparison identifying exactly what content
    is present or missing between the PDF and LaTeX.
    """
    
    # Stop words for vocabulary analysis
    STOP_WORDS = frozenset({
        'the', 'a', 'an', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'be', 
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 
        'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can',
        'of', 'to', 'in', 'for', 'on', 'with', 'at', 'by', 'from', 'as', 'into',
        'through', 'during', 'before', 'after', 'above', 'below', 'between',
        'under', 'again', 'further', 'then', 'once', 'here', 'there', 'when',
        'where', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'it', 'its',
        'this', 'that', 'these', 'those', 'i', 'we', 'you', 'he', 'she', 'they',
        'me', 'us', 'him', 'her', 'them', 'my', 'our', 'your', 'his', 'their',
        'which', 'who', 'whom', 'what', 'if', 'while', 'because', 'although',
    })
    
    def __init__(self):
        self._fitz = None
    
    def _get_fitz(self):
        """Lazy load PyMuPDF."""
        if self._fitz is None:
            try:
                import fitz
                self._fitz = fitz
            except ImportError:
                raise ImportError("PyMuPDF required: pip install PyMuPDF")
        return self._fitz
    
    # ========================================================================
    # MAIN VALIDATION METHOD
    # ========================================================================
    
    def validate(
        self,
        pdf_path: str,
        latex_path: str,
        per_page: bool = True,
    ) -> ValidationReport:
        """
        Perform statistical validation of PDF-to-LaTeX conversion.
        
        Args:
            pdf_path: Path to original PDF file
            latex_path: Path to generated LaTeX file
            per_page: Whether to do page-by-page comparison
            
        Returns:
            ValidationReport with detailed statistics
        """
        report = ValidationReport(pdf_path=pdf_path, latex_path=latex_path)
        
        # Load PDF
        try:
            pdf_text, pdf_pages, pdf_page_texts = self._extract_pdf(pdf_path)
            report.statistics.pdf_total_pages = pdf_pages
        except Exception as e:
            report.critical_issues.append(f"Failed to load PDF: {e}")
            return report
        
        # Load LaTeX
        try:
            latex_content = Path(latex_path).read_text(encoding="utf-8")
            report.statistics.latex_total_lines = latex_content.count('\n') + 1
        except UnicodeDecodeError:
            try:
                latex_content = Path(latex_path).read_text(encoding="latin-1")
                report.warnings.append("LaTeX file read with Latin-1 encoding (not UTF-8)")
            except Exception as e:
                report.critical_issues.append(f"Failed to load LaTeX: {e}")
                return report
        except Exception as e:
            report.critical_issues.append(f"Failed to load LaTeX: {e}")
            return report
        
        # Extract plain text from LaTeX
        latex_text = self._strip_latex_to_text(latex_content)
        
        # ====================================================================
        # WORD AND CHARACTER STATISTICS
        # ====================================================================
        
        pdf_words = self._tokenize(pdf_text)
        latex_words = self._tokenize(latex_text)
        
        report.statistics.pdf_total_words = len(pdf_words)
        report.statistics.latex_total_words = len(latex_words)
        report.statistics.word_difference = len(pdf_words) - len(latex_words)
        
        if len(pdf_words) > 0:
            report.statistics.word_coverage_pct = (len(latex_words) / len(pdf_words)) * 100
        
        report.statistics.pdf_total_chars = len(self._clean_whitespace(pdf_text))
        report.statistics.latex_total_chars = len(self._clean_whitespace(latex_text))
        report.statistics.char_difference = report.statistics.pdf_total_chars - report.statistics.latex_total_chars
        
        if report.statistics.pdf_total_chars > 0:
            report.statistics.char_coverage_pct = (report.statistics.latex_total_chars / report.statistics.pdf_total_chars) * 100
        
        # ====================================================================
        # EQUATION STATISTICS
        # ====================================================================
        
        self._analyze_equations(pdf_text, latex_content, report)
        
        # ====================================================================
        # TABLE STATISTICS
        # ====================================================================
        
        self._analyze_tables(pdf_text, latex_content, report)
        
        # ====================================================================
        # FIGURE STATISTICS
        # ====================================================================
        
        self._analyze_figures(pdf_text, latex_content, report)
        
        # ====================================================================
        # SECTION STATISTICS
        # ====================================================================
        
        self._analyze_sections(pdf_text, latex_content, report)
        
        # ====================================================================
        # LATEX SYNTAX CHECK
        # ====================================================================
        
        report.latex_syntax = self._check_latex_syntax(latex_content)
        
        # ====================================================================
        # VOCABULARY COMPARISON
        # ====================================================================
        
        report.vocabulary = self._compare_vocabulary(pdf_words, latex_words, pdf_text, latex_text)
        
        # ====================================================================
        # ADDITIONAL LATEX STATISTICS
        # ====================================================================
        
        self._analyze_latex_elements(latex_content, report)
        
        # ====================================================================
        # PAGE-BY-PAGE COMPARISON
        # ====================================================================
        
        if per_page and pdf_pages > 0:
            report.page_comparisons = self._compare_pages(
                pdf_page_texts, latex_content, pdf_text, latex_text
            )
            
            # Identify pages with issues
            for pc in report.page_comparisons:
                if pc.status in ("LOW_COVERAGE", "MISSING"):
                    report.pages_with_issues.append(pc.page_number)
        
        # ====================================================================
        # GENERATE WARNINGS
        # ====================================================================
        
        self._generate_warnings(report)
        
        return report
    
    # ========================================================================
    # PDF EXTRACTION
    # ========================================================================
    
    def _extract_pdf(self, pdf_path: str) -> Tuple[str, int, List[str]]:
        """Extract text from PDF."""
        fitz = self._get_fitz()
        
        doc = fitz.open(pdf_path)
        page_texts = []
        
        for page in doc:
            text = page.get_text("text")
            page_texts.append(text)
        
        total_pages = len(doc)
        full_text = "\n\n".join(page_texts)
        doc.close()
        
        return full_text, total_pages, page_texts
    
    # ========================================================================
    # TEXT PROCESSING
    # ========================================================================
    
    def _strip_latex_to_text(self, latex: str) -> str:
        """Strip LaTeX commands to get plain text."""
        text = latex
        
        # Remove comments
        text = re.sub(r'(?<!\\)%.*$', '', text, flags=re.MULTILINE)
        
        # Remove preamble
        doc_start = text.find(r'\begin{document}')
        if doc_start != -1:
            text = text[doc_start + len(r'\begin{document}'):]
        
        doc_end = text.find(r'\end{document}')
        if doc_end != -1:
            text = text[:doc_end]
        
        # Replace commands with their content
        text = re.sub(r'\\textbf\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\textit\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\emph\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\title\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\section\*?\{([^}]*)\}', r'\1', text)
        text = re.sub(r'\\subsection\*?\{([^}]*)\}', r'\1', text)
        
        # Remove environments but keep content
        text = re.sub(r'\\begin\{[^}]+\}', ' ', text)
        text = re.sub(r'\\end\{[^}]+\}', ' ', text)
        
        # Remove remaining commands
        text = re.sub(r'\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?', ' ', text)
        
        # Remove special characters
        text = re.sub(r'[{}$\\&%#_^~]', ' ', text)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into words."""
        text = unicodedata.normalize('NFKC', text)
        words = re.findall(r"\b[a-zA-Z]+(?:[-'][a-zA-Z]+)*\b", text.lower())
        return words
    
    def _clean_whitespace(self, text: str) -> str:
        """Remove all whitespace."""
        return re.sub(r'\s', '', text)
    
    # ========================================================================
    # EQUATION ANALYSIS
    # ========================================================================
    
    def _analyze_equations(self, pdf_text: str, latex: str, report: ValidationReport) -> None:
        """Analyze equations in PDF and LaTeX."""
        stats = report.statistics
        
        # PDF equation detection
        # Numbered equations like (1), (2), (2.1), etc.
        numbered_eqs = re.findall(r'\((\d+(?:\.\d+)?)\)\s*$', pdf_text, re.MULTILINE)
        stats.pdf_numbered_equations = len(numbered_eqs)
        
        # Math indicators in PDF
        math_patterns = [
            r'[a-zA-Z]\s*=\s*[a-zA-Z0-9]',  # a = b
            r'[+-/*]\s*[a-zA-Z]',  # operators with variables
            r'[a-zA-Z]\s*[+-/*]',
            r'[0-9]+\s*[a-zA-Z]',  # coefficient with variable
        ]
        math_indicators = 0
        for pattern in math_patterns:
            math_indicators += len(re.findall(pattern, pdf_text))
        stats.pdf_inline_math_indicators = min(math_indicators, 500)
        
        # Estimate total PDF equations
        stats.pdf_equations_estimated = stats.pdf_numbered_equations + (stats.pdf_inline_math_indicators // 5)
        
        # LaTeX equation detection
        # Inline math $...$
        inline_dollar = re.findall(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)', latex, re.DOTALL)
        stats.latex_inline_equations = len(inline_dollar)
        
        # Inline math \(...\)
        inline_paren = re.findall(r'\\\((.+?)\\\)', latex, re.DOTALL)
        stats.latex_inline_equations += len(inline_paren)
        
        # Display math $$...$$
        display_dollar = re.findall(r'\$\$(.+?)\$\$', latex, re.DOTALL)
        stats.latex_display_equations = len(display_dollar)
        
        # Display math \[...\]
        display_bracket = re.findall(r'\\\[(.+?)\\\]', latex, re.DOTALL)
        stats.latex_display_equations += len(display_bracket)
        
        # Equation environments
        eq_envs = re.findall(r'\\begin\{(equation|align|gather|multline|eqnarray)\*?\}', latex)
        stats.latex_equation_environments = len(eq_envs)
        
        # Total LaTeX equations
        stats.latex_total_equations = (
            stats.latex_inline_equations + 
            stats.latex_display_equations + 
            stats.latex_equation_environments
        )
        
        # Difference
        stats.equation_difference = stats.pdf_equations_estimated - stats.latex_total_equations
    
    # ========================================================================
    # TABLE ANALYSIS
    # ========================================================================
    
    def _analyze_tables(self, pdf_text: str, latex: str, report: ValidationReport) -> None:
        """Analyze tables in PDF and LaTeX."""
        stats = report.statistics
        
        # PDF table detection
        table_refs = []
        
        # "Table 1", "TABLE I", "Table 2.1", etc.
        table_patterns = [
            r'Table\s+(\d+(?:\.\d+)?)',
            r'TABLE\s+([IVX]+|\d+)',
            r'Tab\.\s*(\d+)',
        ]
        
        for pattern in table_patterns:
            matches = re.findall(pattern, pdf_text, re.IGNORECASE)
            for m in matches:
                ref = f"Table {m}"
                if ref not in table_refs:
                    table_refs.append(ref)
        
        stats.pdf_table_references = table_refs
        stats.pdf_tables_detected = len(set(table_refs))
        
        # LaTeX table detection
        stats.latex_tables = len(re.findall(r'\\begin\{table\}', latex))
        stats.latex_tabular_environments = len(re.findall(r'\\begin\{tabular\}', latex))
        stats.latex_tabular_environments += len(re.findall(r'\\begin\{longtable\}', latex))
        
        # Difference
        latex_table_count = max(stats.latex_tables, stats.latex_tabular_environments)
        stats.table_difference = stats.pdf_tables_detected - latex_table_count
        
        # Find missing tables
        if stats.table_difference > 0:
            # Check which table references are not in LaTeX
            latex_lower = latex.lower()
            for ref in table_refs:
                # Check if table number appears in LaTeX
                num = re.search(r'\d+', ref)
                if num:
                    if f"table {num.group()}" not in latex_lower:
                        if ref not in stats.missing_tables:
                            stats.missing_tables.append(ref)
    
    # ========================================================================
    # FIGURE ANALYSIS
    # ========================================================================
    
    def _analyze_figures(self, pdf_text: str, latex: str, report: ValidationReport) -> None:
        """Analyze figures in PDF and LaTeX."""
        stats = report.statistics
        
        # PDF figure detection
        figure_refs = []
        
        # "Figure 1", "Fig. 2", "FIGURE 3", etc.
        figure_patterns = [
            r'Figure\s+(\d+(?:\.\d+)?)',
            r'Fig\.\s*(\d+(?:\.\d+)?)',
            r'FIGURE\s+(\d+)',
        ]
        
        for pattern in figure_patterns:
            matches = re.findall(pattern, pdf_text, re.IGNORECASE)
            for m in matches:
                ref = f"Figure {m}"
                if ref not in figure_refs:
                    figure_refs.append(ref)
        
        stats.pdf_figure_references = figure_refs
        stats.pdf_figures_detected = len(set(figure_refs))
        
        # LaTeX figure detection
        stats.latex_figures = len(re.findall(r'\\begin\{figure\}', latex))
        stats.latex_includegraphics = len(re.findall(r'\\includegraphics', latex))
        
        # Difference
        latex_figure_count = max(stats.latex_figures, stats.latex_includegraphics)
        stats.figure_difference = stats.pdf_figures_detected - latex_figure_count
        
        # Find missing figures
        if stats.figure_difference > 0:
            latex_lower = latex.lower()
            for ref in figure_refs:
                num = re.search(r'\d+', ref)
                if num:
                    if f"figure {num.group()}" not in latex_lower and f"fig {num.group()}" not in latex_lower:
                        if ref not in stats.missing_figures:
                            stats.missing_figures.append(ref)
    
    # ========================================================================
    # SECTION ANALYSIS
    # ========================================================================
    
    def _analyze_sections(self, pdf_text: str, latex: str, report: ValidationReport) -> None:
        """Analyze sections in PDF and LaTeX."""
        stats = report.statistics
        
        # PDF section detection
        section_titles = []
        
        # Common section patterns
        section_patterns = [
            r'^(\d+\.)\s+([A-Z][A-Za-z\s]+)$',  # "1. Introduction"
            r'^(\d+\.\d+)\s+([A-Z][A-Za-z\s]+)$',  # "1.1 Background"
            r'^([IVX]+\.)\s+([A-Z][A-Za-z\s]+)$',  # "I. Introduction"
            r'^(Chapter\s+\d+)\s*[:\.]?\s*(.+)$',  # "Chapter 1: Title"
            r'^([A-Z][A-Z\s]{5,})$',  # ALL CAPS HEADERS
        ]
        
        for pattern in section_patterns:
            matches = re.findall(pattern, pdf_text, re.MULTILINE)
            for m in matches:
                if isinstance(m, tuple):
                    title = ' '.join(m).strip()
                else:
                    title = m.strip()
                if len(title) > 3 and title not in section_titles:
                    section_titles.append(title[:50])
        
        stats.pdf_section_titles = section_titles[:20]
        stats.pdf_sections_estimated = len(section_titles)
        
        # LaTeX section detection
        stats.latex_sections = len(re.findall(r'\\section\*?\s*\{', latex))
        stats.latex_subsections = len(re.findall(r'\\subsection\*?\s*\{', latex))
        stats.latex_subsubsections = len(re.findall(r'\\subsubsection\*?\s*\{', latex))
        stats.latex_total_sections = (
            stats.latex_sections + 
            stats.latex_subsections + 
            stats.latex_subsubsections
        )
        
        # Difference
        stats.section_difference = stats.pdf_sections_estimated - stats.latex_total_sections
        
        # Find potentially missing sections
        if stats.section_difference > 0:
            # Extract LaTeX section titles
            latex_titles = re.findall(r'\\section\*?\{([^}]+)\}', latex, re.IGNORECASE)
            latex_titles_lower = [t.lower() for t in latex_titles]
            
            for pdf_title in section_titles:
                # Check if any words from PDF title appear in LaTeX titles
                pdf_words = set(pdf_title.lower().split())
                found = False
                for latex_title in latex_titles_lower:
                    latex_words = set(latex_title.split())
                    if len(pdf_words & latex_words) >= 1:
                        found = True
                        break
                
                if not found and pdf_title not in stats.missing_sections:
                    stats.missing_sections.append(pdf_title)
    
    # ========================================================================
    # LATEX SYNTAX CHECK
    # ========================================================================
    
    def _check_latex_syntax(self, latex: str) -> LatexSyntaxCheck:
        """Check LaTeX syntax for validity."""
        check = LatexSyntaxCheck()
        
        # Document structure
        check.has_document_class = bool(re.search(r'\\documentclass', latex))
        check.has_begin_document = bool(re.search(r'\\begin\{document\}', latex))
        check.has_end_document = bool(re.search(r'\\end\{document\}', latex))
        
        # Extract packages
        packages = re.findall(r'\\usepackage\s*(?:\[.*?\])?\s*\{([^}]+)\}', latex)
        for pkg_group in packages:
            for pkg in pkg_group.split(','):
                check.packages_used.append(pkg.strip())
        
        # Brace balance
        clean = re.sub(r'\\[{}]', '', latex)  # Remove \{ and \}
        check.open_braces = clean.count('{')
        check.close_braces = clean.count('}')
        check.brace_difference = check.open_braces - check.close_braces
        check.braces_balanced = check.brace_difference == 0
        
        if not check.braces_balanced:
            check.syntax_issues.append(
                f"Unbalanced braces: {check.open_braces} open, {check.close_braces} close"
            )
        
        # Environment balance
        begins = re.findall(r'\\begin\{([^}]+)\}', latex)
        ends = re.findall(r'\\end\{([^}]+)\}', latex)
        
        check.begin_environments = len(begins)
        check.end_environments = len(ends)
        
        begin_counter = Counter(begins)
        end_counter = Counter(ends)
        
        for env, count in begin_counter.items():
            end_count = end_counter.get(env, 0)
            if count != end_count:
                check.unbalanced_environments.append(f"{env}: {count} begin, {end_count} end")
        
        check.environments_balanced = len(check.unbalanced_environments) == 0
        
        # Math delimiter balance
        inline_delims = len(re.findall(r'(?<!\$)\$(?!\$)', latex))
        check.inline_math_delimiters = inline_delims
        check.math_balanced = inline_delims % 2 == 0
        
        if not check.math_balanced:
            check.syntax_issues.append(f"Unbalanced $ delimiters: {inline_delims} found (should be even)")
        
        # Overall validity
        check.is_valid = (
            check.braces_balanced and 
            check.environments_balanced and 
            check.math_balanced
        )
        
        return check
    
    # ========================================================================
    # VOCABULARY COMPARISON
    # ========================================================================
    
    def _compare_vocabulary(
        self,
        pdf_words: List[str],
        latex_words: List[str],
        pdf_text: str,
        latex_text: str,
    ) -> VocabularyComparison:
        """Compare vocabulary between PDF and LaTeX."""
        comp = VocabularyComparison()
        
        pdf_set = set(pdf_words)
        latex_set = set(latex_words)
        
        comp.pdf_unique_words = len(pdf_set)
        comp.latex_unique_words = len(latex_set)
        comp.shared_words = len(pdf_set & latex_set)
        comp.words_only_in_pdf = len(pdf_set - latex_set)
        comp.words_only_in_latex = len(latex_set - pdf_set)
        
        if pdf_set:
            comp.vocabulary_overlap_pct = (len(pdf_set & latex_set) / len(pdf_set | latex_set)) * 100
        
        # Word frequencies
        pdf_freq = Counter(pdf_words)
        latex_freq = Counter(latex_words)
        
        # Top content words
        pdf_content = [(w, c) for w, c in pdf_freq.most_common(150) 
                       if w not in self.STOP_WORDS and len(w) > 2]
        latex_content = [(w, c) for w, c in latex_freq.most_common(150)
                        if w not in self.STOP_WORDS and len(w) > 2]
        
        comp.top_pdf_terms = pdf_content[:15]
        comp.top_latex_terms = latex_content[:15]
        
        # Missing key terms
        top_pdf_set = set(w for w, _ in pdf_content[:50])
        comp.missing_key_terms = [w for w in top_pdf_set if w not in latex_set]
        
        # Numbers comparison
        pdf_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', pdf_text))
        latex_numbers = set(re.findall(r'\b\d+(?:\.\d+)?\b', latex_text))
        
        comp.pdf_numbers = len(pdf_numbers)
        comp.latex_numbers = len(latex_numbers)
        
        if pdf_numbers:
            matched = len(pdf_numbers & latex_numbers)
            comp.numbers_matched_pct = (matched / len(pdf_numbers)) * 100
        
        # Technical terms (capitalized)
        pdf_tech = set(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', pdf_text))
        latex_tech = set(re.findall(r'\b[A-Z][a-z]+(?:[A-Z][a-z]+)*\b', latex_text))
        
        comp.pdf_technical_terms = len(pdf_tech)
        comp.latex_technical_terms = len(latex_tech)
        
        if pdf_tech:
            matched = len(pdf_tech & latex_tech)
            comp.technical_terms_matched_pct = (matched / len(pdf_tech)) * 100
        
        return comp
    
    # ========================================================================
    # ADDITIONAL LATEX STATISTICS
    # ========================================================================
    
    def _analyze_latex_elements(self, latex: str, report: ValidationReport) -> None:
        """Analyze additional LaTeX elements."""
        stats = report.statistics
        
        # Lists
        stats.latex_itemize_lists = len(re.findall(r'\\begin\{itemize\}', latex))
        stats.latex_enumerate_lists = len(re.findall(r'\\begin\{enumerate\}', latex))
        stats.latex_total_list_items = len(re.findall(r'\\item(?:\[|\s|$)', latex))
        
        # References
        stats.latex_labels = len(re.findall(r'\\label\s*\{', latex))
        stats.latex_refs = len(re.findall(r'\\(?:ref|eqref|pageref)\s*\{', latex))
        stats.latex_citations = len(re.findall(r'\\cite\w*\s*(?:\[.*?\])?\s*\{', latex))
        stats.latex_footnotes = len(re.findall(r'\\footnote\s*\{', latex))
        
        # Math elements
        stats.latex_greek_letters = len(re.findall(
            r'\\(?:alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|'
            r'lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega)\b', 
            latex, re.IGNORECASE
        ))
        stats.latex_fractions = len(re.findall(r'\\frac\s*\{', latex))
        stats.latex_integrals = len(re.findall(r'\\int(?:_|\\limits)?', latex))
        stats.latex_summations = len(re.findall(r'\\sum(?:_|\\limits)?', latex))
        stats.latex_subscripts = len(re.findall(r'_\{', latex))
        stats.latex_superscripts = len(re.findall(r'\^\{', latex))
    
    # ========================================================================
    # PAGE-BY-PAGE COMPARISON
    # ========================================================================
    
    def _compare_pages(
        self,
        pdf_page_texts: List[str],
        latex_content: str,
        full_pdf_text: str,
        full_latex_text: str,
    ) -> List[PageComparison]:
        """Compare content page by page."""
        latex_blocks = self._split_latex_by_page(latex_content, len(pdf_page_texts))
        
        comparisons = []
        
        for i, (pdf_text, latex_block) in enumerate(zip(pdf_page_texts, latex_blocks)):
            latex_plain = self._strip_latex_to_text(latex_block)
            
            pdf_words = self._tokenize(pdf_text)
            latex_words = self._tokenize(latex_plain)
            
            pc = PageComparison(page_number=i + 1)
            
            # Word stats
            pc.pdf_words = len(pdf_words)
            pc.latex_words = len(latex_words)
            pc.word_difference = pc.pdf_words - pc.latex_words
            pc.word_coverage_pct = (pc.latex_words / pc.pdf_words * 100) if pc.pdf_words > 0 else 0
            
            # Char stats
            pc.pdf_chars = len(self._clean_whitespace(pdf_text))
            pc.latex_chars = len(self._clean_whitespace(latex_plain))
            pc.char_difference = pc.pdf_chars - pc.latex_chars
            pc.char_coverage_pct = (pc.latex_chars / pc.pdf_chars * 100) if pc.pdf_chars > 0 else 0
            
            # Element counts
            pc.pdf_equations = len(re.findall(r'\(\d+\)', pdf_text))
            pc.latex_equations = len(re.findall(r'\$', latex_block)) // 2
            
            pc.pdf_tables = len(re.findall(r'Table\s+\d+', pdf_text, re.IGNORECASE))
            pc.latex_tables = len(re.findall(r'\\begin\{tabular\}', latex_block))
            
            pc.pdf_figures = len(re.findall(r'Fig(?:ure)?\.?\s*\d+', pdf_text, re.IGNORECASE))
            pc.latex_figures = len(re.findall(r'\\includegraphics', latex_block))
            
            # Similarity
            if len(pdf_text) > 10 and len(latex_plain) > 10:
                pc.similarity_pct = SequenceMatcher(
                    None, 
                    pdf_text[:5000].lower(), 
                    latex_plain[:5000].lower()
                ).ratio() * 100
            
            # Status determination
            if pc.word_coverage_pct >= 80:
                pc.status = "OK"
            elif pc.word_coverage_pct >= 60:
                pc.status = "PARTIAL"
            elif pc.word_coverage_pct >= 30:
                pc.status = "LOW_COVERAGE"
            else:
                pc.status = "MISSING"
            
            # Missing content keywords
            pdf_word_set = set(pdf_words)
            latex_word_set = set(latex_words)
            missing = pdf_word_set - latex_word_set - self.STOP_WORDS
            
            # Get most frequent missing words
            pdf_freq = Counter(pdf_words)
            missing_freq = [(w, pdf_freq[w]) for w in missing if len(w) > 3]
            missing_freq.sort(key=lambda x: -x[1])
            pc.missing_content_keywords = [w for w, _ in missing_freq[:10]]
            
            pc.missing_equations = max(0, pc.pdf_equations - pc.latex_equations)
            
            comparisons.append(pc)
        
        return comparisons
    
    def _split_latex_by_page(self, latex: str, num_pages: int) -> List[str]:
        """Split LaTeX content into page-sized blocks."""
        markers = ['% --- Page Break ---', '\\newpage', '\\pagebreak', '\\clearpage']
        
        for marker in markers:
            if marker in latex:
                blocks = latex.split(marker)
                if len(blocks) >= num_pages * 0.5:
                    break
        else:
            # Extract body
            body_match = re.search(r'\\begin\{document\}(.*?)\\end\{document\}', latex, re.DOTALL)
            body = body_match.group(1) if body_match else latex
            
            lines = body.split('\n')
            lines_per_page = max(1, len(lines) // num_pages)
            
            blocks = []
            for i in range(0, len(lines), lines_per_page):
                blocks.append('\n'.join(lines[i:i + lines_per_page]))
        
        while len(blocks) < num_pages:
            blocks.append('')
        
        return blocks[:num_pages]
    
    # ========================================================================
    # WARNING GENERATION
    # ========================================================================
    
    def _generate_warnings(self, report: ValidationReport) -> None:
        """Generate warnings based on statistics."""
        stats = report.statistics
        
        # Word coverage
        if stats.word_coverage_pct < 50:
            report.critical_issues.append(
                f"Very low word coverage: {stats.word_coverage_pct:.1f}% - significant content missing"
            )
        elif stats.word_coverage_pct < 70:
            report.warnings.append(
                f"Low word coverage: {stats.word_coverage_pct:.1f}% - some content may be missing"
            )
        
        # Missing tables
        if stats.missing_tables:
            report.warnings.append(
                f"Missing tables: {', '.join(stats.missing_tables[:5])}"
            )
        
        # Missing figures
        if stats.missing_figures:
            report.warnings.append(
                f"Missing figures: {', '.join(stats.missing_figures[:5])}"
            )
        
        # Missing sections
        if stats.missing_sections:
            report.warnings.append(
                f"Potentially missing sections: {', '.join(stats.missing_sections[:3])}"
            )
        
        # LaTeX syntax
        if not report.latex_syntax.is_valid:
            for issue in report.latex_syntax.syntax_issues:
                report.critical_issues.append(f"LaTeX syntax: {issue}")
        
        # Vocabulary
        if report.vocabulary.missing_key_terms:
            terms = ', '.join(report.vocabulary.missing_key_terms[:5])
            report.warnings.append(f"Missing key terms: {terms}")
        
        # Number preservation
        if report.vocabulary.numbers_matched_pct < 60 and report.vocabulary.pdf_numbers > 10:
            report.warnings.append(
                f"Low number preservation: {report.vocabulary.numbers_matched_pct:.0f}%"
            )
    
    # ========================================================================
    # REPORT FORMATTING
    # ========================================================================
    
    def print_report(self, report: ValidationReport, detailed: bool = True) -> str:
        """Generate formatted text report."""
        lines = []
        stats = report.statistics
        
        lines.extend([
            "=" * 80,
            "PDF-to-LaTeX Statistical Comparison Report",
            "=" * 80,
            "",
            f"PDF:   {report.pdf_path}",
            f"LaTeX: {report.latex_path}",
            f"Time:  {report.validation_time}",
            "",
        ])
        
        # ================================================================
        # DOCUMENT STATISTICS
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "DOCUMENT STATISTICS",
            "-" * 80,
            "",
            f"  PDF:",
            f"    Pages:                           {stats.pdf_total_pages}",
            f"    Words:                           {stats.pdf_total_words:,}",
            f"    Characters:                      {stats.pdf_total_chars:,}",
            "",
            f"  LaTeX:",
            f"    Lines of code:                   {stats.latex_total_lines}",
            f"    Words (text content):            {stats.latex_total_words:,}",
            f"    Characters (text content):       {stats.latex_total_chars:,}",
            "",
            f"  Coverage:",
            f"    Words in LaTeX / Words in PDF:   {stats.latex_total_words:,} / {stats.pdf_total_words:,} = {stats.word_coverage_pct:.1f}%",
            f"    Chars in LaTeX / Chars in PDF:   {stats.latex_total_chars:,} / {stats.pdf_total_chars:,} = {stats.char_coverage_pct:.1f}%",
            f"    Missing words:                   {stats.word_difference:,}",
            f"    Missing characters:              {stats.char_difference:,}",
            "",
        ])
        
        # ================================================================
        # EQUATION STATISTICS
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "EQUATION STATISTICS",
            "-" * 80,
            "",
            f"  PDF Analysis:",
            f"    Numbered equations detected:     {stats.pdf_numbered_equations}",
            f"    Math expression indicators:      {stats.pdf_inline_math_indicators}",
            f"    Estimated total equations:       {stats.pdf_equations_estimated}",
            "",
            f"  LaTeX Analysis:",
            f"    Inline equations ($...$):        {stats.latex_inline_equations}",
            f"    Display equations ($$, \\[\\]):    {stats.latex_display_equations}",
            f"    Equation environments:           {stats.latex_equation_environments}",
            f"    Total LaTeX equations:           {stats.latex_total_equations}",
            "",
            f"  Comparison:",
            f"    Difference (PDF - LaTeX):        {stats.equation_difference:+d}",
            "",
        ])
        
        # ================================================================
        # TABLE STATISTICS
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "TABLE STATISTICS",
            "-" * 80,
            "",
            f"  PDF Analysis:",
            f"    Tables detected:                 {stats.pdf_tables_detected}",
        ])
        
        if stats.pdf_table_references:
            refs = ', '.join(stats.pdf_table_references[:10])
            lines.append(f"    References found:                {refs}")
        
        lines.extend([
            "",
            f"  LaTeX Analysis:",
            f"    Table environments:              {stats.latex_tables}",
            f"    Tabular environments:            {stats.latex_tabular_environments}",
            "",
            f"  Comparison:",
            f"    Difference (PDF - LaTeX):        {stats.table_difference:+d}",
        ])
        
        if stats.missing_tables:
            lines.append(f"    MISSING TABLES:                  {', '.join(stats.missing_tables)}")
        else:
            lines.append(f"    Missing tables:                  None detected")
        
        lines.append("")
        
        # ================================================================
        # FIGURE STATISTICS
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "FIGURE STATISTICS",
            "-" * 80,
            "",
            f"  PDF Analysis:",
            f"    Figures detected:                {stats.pdf_figures_detected}",
        ])
        
        if stats.pdf_figure_references:
            refs = ', '.join(stats.pdf_figure_references[:10])
            lines.append(f"    References found:                {refs}")
        
        lines.extend([
            "",
            f"  LaTeX Analysis:",
            f"    Figure environments:             {stats.latex_figures}",
            f"    \\includegraphics commands:       {stats.latex_includegraphics}",
            "",
            f"  Comparison:",
            f"    Difference (PDF - LaTeX):        {stats.figure_difference:+d}",
        ])
        
        if stats.missing_figures:
            missing = ', '.join(stats.missing_figures[:10])
            lines.append(f"    MISSING FIGURES:                 {missing}")
        else:
            lines.append(f"    Missing figures:                 None detected")
        
        lines.append("")
        
        # ================================================================
        # SECTION STATISTICS
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "SECTION STATISTICS",
            "-" * 80,
            "",
            f"  PDF Analysis:",
            f"    Sections estimated:              {stats.pdf_sections_estimated}",
        ])
        
        if stats.pdf_section_titles:
            lines.append(f"    Section titles found:")
            for title in stats.pdf_section_titles[:8]:
                lines.append(f"      - {title}")
        
        lines.extend([
            "",
            f"  LaTeX Analysis:",
            f"    \\section commands:               {stats.latex_sections}",
            f"    \\subsection commands:            {stats.latex_subsections}",
            f"    \\subsubsection commands:         {stats.latex_subsubsections}",
            f"    Total sectioning:                {stats.latex_total_sections}",
            "",
            f"  Comparison:",
            f"    Difference (PDF - LaTeX):        {stats.section_difference:+d}",
        ])
        
        if stats.missing_sections:
            lines.append(f"    POTENTIALLY MISSING:")
            for sec in stats.missing_sections[:5]:
                lines.append(f"      - {sec}")
        
        lines.append("")
        
        # ================================================================
        # LATEX SYNTAX CHECK
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "LATEX SYNTAX VALIDATION",
            "-" * 80,
            "",
            f"  Document Structure:",
            f"    Has \\documentclass:              {'Yes' if report.latex_syntax.has_document_class else 'No'}",
            f"    Has \\begin{{document}}:           {'Yes' if report.latex_syntax.has_begin_document else 'No'}",
            f"    Has \\end{{document}}:             {'Yes' if report.latex_syntax.has_end_document else 'No'}",
            "",
            f"  Balance Checks:",
            f"    Braces: {report.latex_syntax.open_braces} open, {report.latex_syntax.close_braces} close",
            f"    Braces balanced:                 {'Yes' if report.latex_syntax.braces_balanced else 'NO - ISSUE'}",
            f"    Environments balanced:           {'Yes' if report.latex_syntax.environments_balanced else 'NO - ISSUE'}",
            f"    Math delimiters balanced:        {'Yes' if report.latex_syntax.math_balanced else 'NO - ISSUE'}",
            "",
            f"  Overall Syntax Valid:              {'Yes' if report.latex_syntax.is_valid else 'NO - HAS ISSUES'}",
        ])
        
        if report.latex_syntax.unbalanced_environments:
            lines.append(f"    Unbalanced environments:")
            for env in report.latex_syntax.unbalanced_environments:
                lines.append(f"      - {env}")
        
        if report.latex_syntax.packages_used:
            lines.append(f"  Packages used ({len(report.latex_syntax.packages_used)}):")
            lines.append(f"    {', '.join(report.latex_syntax.packages_used[:15])}")
        
        lines.append("")
        
        # ================================================================
        # VOCABULARY COMPARISON
        # ================================================================
        
        lines.extend([
            "-" * 80,
            "VOCABULARY COMPARISON",
            "-" * 80,
            "",
            f"  Word Statistics:",
            f"    Unique words in PDF:             {report.vocabulary.pdf_unique_words:,}",
            f"    Unique words in LaTeX:           {report.vocabulary.latex_unique_words:,}",
            f"    Words in both:                   {report.vocabulary.shared_words:,}",
            f"    Words only in PDF:               {report.vocabulary.words_only_in_pdf:,}",
            f"    Words only in LaTeX:             {report.vocabulary.words_only_in_latex:,}",
            f"    Vocabulary overlap:              {report.vocabulary.vocabulary_overlap_pct:.1f}%",
            "",
            f"  Number Preservation:",
            f"    Numbers in PDF:                  {report.vocabulary.pdf_numbers}",
            f"    Numbers in LaTeX:                {report.vocabulary.latex_numbers}",
            f"    Numbers matched:                 {report.vocabulary.numbers_matched_pct:.1f}%",
            "",
        ])
        
        if report.vocabulary.missing_key_terms:
            lines.append(f"  Missing Key Terms (top PDF words not in LaTeX):")
            terms = ', '.join(report.vocabulary.missing_key_terms[:15])
            lines.append(f"    {terms}")
            lines.append("")
        
        # ================================================================
        # LATEX ELEMENT COUNTS
        # ================================================================
        
        if detailed:
            lines.extend([
                "-" * 80,
                "LATEX ELEMENT COUNTS",
                "-" * 80,
                "",
                f"  Lists:",
                f"    Itemize lists:                   {stats.latex_itemize_lists}",
                f"    Enumerate lists:                 {stats.latex_enumerate_lists}",
                f"    Total list items:                {stats.latex_total_list_items}",
                "",
                f"  References:",
                f"    Labels (\\label):                 {stats.latex_labels}",
                f"    References (\\ref):               {stats.latex_refs}",
                f"    Citations (\\cite):               {stats.latex_citations}",
                f"    Footnotes:                       {stats.latex_footnotes}",
                "",
                f"  Math Elements:",
                f"    Greek letters:                   {stats.latex_greek_letters}",
                f"    Fractions (\\frac):               {stats.latex_fractions}",
                f"    Integrals (\\int):                {stats.latex_integrals}",
                f"    Summations (\\sum):               {stats.latex_summations}",
                f"    Subscripts:                      {stats.latex_subscripts}",
                f"    Superscripts:                    {stats.latex_superscripts}",
                "",
            ])
        
        # ================================================================
        # PAGE-BY-PAGE COMPARISON
        # ================================================================
        
        if report.page_comparisons:
            lines.extend([
                "-" * 80,
                "PAGE-BY-PAGE COMPARISON",
                "-" * 80,
                "",
                f"  {'Page':<6} {'PDF Words':<12} {'LaTeX Words':<14} {'Coverage':<12} {'Similarity':<12} {'Status':<12}",
                f"  {'-'*68}",
            ])
            
            for pc in report.page_comparisons:
                status_marker = ""
                if pc.status == "LOW_COVERAGE":
                    status_marker = " [!]"
                elif pc.status == "MISSING":
                    status_marker = " [!!]"
                
                lines.append(
                    f"  {pc.page_number:<6} {pc.pdf_words:<12,} {pc.latex_words:<14,} "
                    f"{pc.word_coverage_pct:>10.1f}% {pc.similarity_pct:>10.1f}% {pc.status:<12}{status_marker}"
                )
            
            lines.append("")
            
            # Pages with issues detail
            problem_pages = [pc for pc in report.page_comparisons if pc.status in ("LOW_COVERAGE", "MISSING")]
            if problem_pages:
                lines.extend([
                    "  Pages with Coverage Issues:",
                    "",
                ])
                for pc in problem_pages[:5]:
                    lines.append(f"    Page {pc.page_number}: {pc.word_coverage_pct:.1f}% coverage, {pc.word_difference:+d} words")
                    if pc.missing_content_keywords:
                        keywords = ', '.join(pc.missing_content_keywords[:8])
                        lines.append(f"      Missing keywords: {keywords}")
                lines.append("")
        
        # ================================================================
        # ISSUES SUMMARY
        # ================================================================
        
        if report.critical_issues or report.warnings:
            lines.extend([
                "-" * 80,
                "ISSUES SUMMARY",
                "-" * 80,
                "",
            ])
            
            if report.critical_issues:
                lines.append("  Critical Issues:")
                for issue in report.critical_issues:
                    lines.append(f"    [!] {issue}")
                lines.append("")
            
            if report.warnings:
                lines.append("  Warnings:")
                for warning in report.warnings:
                    lines.append(f"    [-] {warning}")
                lines.append("")
        
        lines.append("=" * 80)
        
        return "\n".join(lines)


# ============================================================================
# CONVENIENCE FUNCTION
# ============================================================================

def validate_conversion(
    pdf_path: str,
    latex_path: str,
    verbose: bool = True,
    detailed: bool = True,
) -> ValidationReport:
    """
    Validate a PDF-to-LaTeX conversion with statistical comparison.
    
    Args:
        pdf_path: Path to original PDF
        latex_path: Path to generated LaTeX
        verbose: Print report to console
        detailed: Include detailed element counts
        
    Returns:
        ValidationReport with statistics
    """
    validator = ConversionValidator()
    report = validator.validate(pdf_path, latex_path)
    
    if verbose:
        print(validator.print_report(report, detailed=detailed))
    
    return report
