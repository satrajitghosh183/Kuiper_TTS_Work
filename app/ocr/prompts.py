"""
Specialized prompts for different OCR tasks.
"""

from __future__ import annotations


def get_page_conversion_prompt(
    page_num: int,
    total_pages: int,
    extract_images: bool = True,
    is_first_page: bool = False,
    is_last_page: bool = False,
) -> str:
    """
    Generate prompt for converting a PDF page to LaTeX.

    Args:
        page_num: Current page number (1-indexed)
        total_pages: Total number of pages
        extract_images: Whether images will be extracted
        is_first_page: Whether this is the first page
        is_last_page: Whether this is the last page

    Returns:
        Formatted prompt string
    """
    image_instruction = (
        """4. FIGURES: Mark figure locations with:
   \\begin{figure}[h]
   \\centering
   \\includegraphics[width=0.8\\textwidth]{figures/figure_PAGE_NUM.png}
   \\caption{...}
   \\end{figure}"""
        if extract_images
        else "4. FIGURES: Skip figures, just note their presence with a comment"
    )

    first_page_note = (
        """
SPECIAL: This is the first page. Look for:
- Document title (use \\title{} and \\maketitle)
- Author information (use \\author{})
- Abstract (use \\begin{abstract}...\\end{abstract})
"""
        if is_first_page
        else ""
    )

    last_page_note = (
        """
SPECIAL: This is the last page. Look for:
- Bibliography/References (use \\begin{thebibliography} or note for BibTeX)
- Appendices
"""
        if is_last_page
        else ""
    )

    return f"""You are converting page {page_num} of {total_pages} to LaTeX.

TASK: Convert this page to LaTeX source code.
{first_page_note}{last_page_note}
INSTRUCTIONS:
1. EQUATIONS: Convert all mathematical content to LaTeX math mode
   - Inline math: $equation$
   - Display math: \\begin{{equation}} ... \\end{{equation}}
   - Use amsmath environments (align, gather, etc.) for multi-line

2. STRUCTURE:
   - Detect and use \\section{{}}, \\subsection{{}}, etc.
   - Preserve paragraph breaks
   - Convert lists to itemize/enumerate

3. TABLES: Use tabular with booktabs
   \\begin{{table}}[h]
   \\centering
   \\begin{{tabular}}{{columns}}
   \\toprule
   ...
   \\bottomrule
   \\end{{tabular}}
   \\caption{{...}}
   \\end{{table}}

{image_instruction}

5. FORMATTING:
   - Bold: \\textbf{{...}}
   - Italic: \\textit{{...}}
   - Code: \\texttt{{...}}
   - Underline: \\underline{{...}}

6. SPECIAL ELEMENTS:
   - Footnotes: \\footnote{{...}}
   - Citations: \\cite{{...}} (use placeholder keys)
   - Cross-references: \\ref{{...}}, \\label{{...}}

OUTPUT: Return ONLY the LaTeX content for this page. 
No preamble, no \\documentclass, no \\begin{{document}}.
Just the body content."""


EQUATION_EXTRACTION_PROMPT = """Extract ONLY the mathematical equations from this image.

For each equation:
1. Convert to proper LaTeX syntax
2. Use appropriate environment:
   - Inline: $...$
   - Display: \\begin{equation} ... \\end{equation}
   - Multi-line: \\begin{align} ... \\end{align}
   - Cases: \\begin{cases} ... \\end{cases}

3. Use standard LaTeX commands:
   - Fractions: \\frac{num}{den}
   - Subscripts: x_{sub}
   - Superscripts: x^{sup}
   - Greek letters: \\alpha, \\beta, \\gamma, etc.
   - Operators: \\sum, \\int, \\prod, \\lim
   - Matrices: \\begin{bmatrix} ... \\end{bmatrix}
   - Roots: \\sqrt{}, \\sqrt[n]{}
   - Vectors: \\vec{}, \\mathbf{}

4. For numbered equations, include labels:
   \\begin{equation}\\label{eq:name}
   ...
   \\end{equation}

Return ONLY the LaTeX equations, one per line.
Do not include any explanations or commentary."""


TABLE_EXTRACTION_PROMPT = """Extract the table from this image and convert to LaTeX.

Use this format:
\\begin{table}[h]
\\centering
\\caption{TABLE CAPTION HERE}
\\label{tab:label}
\\begin{tabular}{COLUMN_SPEC}
\\toprule
HEADER ROW \\\\
\\midrule
DATA ROWS \\\\
...
\\bottomrule
\\end{tabular}
\\end{table}

Rules:
- Detect column alignment (l=left, c=center, r=right)
- Use \\toprule, \\midrule, \\bottomrule from booktabs
- Use & for column separators
- Use \\\\ for row endings
- Escape special characters: %, $, &, #, _
- For merged cells: \\multicolumn{n}{alignment}{content}
- For multi-row cells: \\multirow{n}{width}{content}
- For long tables, use longtable environment

Return ONLY the LaTeX table code."""


FIGURE_CAPTION_PROMPT = """Describe this figure for a LaTeX caption.

Requirements:
1. Be concise but informative (1-2 sentences maximum)
2. Focus on WHAT the figure shows, not interpretation
3. Include key visual elements (axes labels, legend items, etc.)
4. Do not start with "This figure shows" or "The figure depicts"
5. Use technical language appropriate for academic papers

Examples of good captions:
- "Comparison of model accuracy across three datasets with 95% confidence intervals."
- "Architecture of the proposed neural network with attention mechanism."
- "Temperature variation over time showing seasonal patterns."

Return ONLY the caption text, no LaTeX commands."""


STRUCTURE_ANALYSIS_PROMPT = """Analyze the structure of this document page.

Identify and list:
1. DOCUMENT TYPE: (article, report, book, letter, presentation)
2. SECTIONS: List all section/subsection headings found
3. SPECIAL ELEMENTS:
   - Title and authors (if present)
   - Abstract (if present)
   - Keywords (if present)
   - Equations (count)
   - Tables (count)
   - Figures (count)
   - Citations/References (if present)
   - Footnotes (count)
4. LAYOUT: (single column, two column, mixed)
5. LANGUAGE: Primary language of the document

Format your response as:
TYPE: <document type>
LAYOUT: <layout>
LANGUAGE: <language>
SECTIONS:
- <section 1>
- <section 2>
ELEMENTS:
- equations: <count>
- tables: <count>
- figures: <count>
- footnotes: <count>
SPECIAL:
- title: <yes/no>
- abstract: <yes/no>
- bibliography: <yes/no>"""


CODE_EXTRACTION_PROMPT = """Extract code blocks from this document page.

For each code block:
1. Identify the programming language
2. Extract the code exactly as shown
3. Format using lstlisting or minted environment

Format:
\\begin{lstlisting}[language=LANG, caption=CAPTION]
CODE HERE
\\end{lstlisting}

Or for inline code: \\texttt{code}

Preserve:
- Indentation
- Comments
- Line breaks
- Special characters (escape if needed)

Return ONLY the LaTeX code blocks."""

