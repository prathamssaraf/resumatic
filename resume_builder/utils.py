"""
Shared utilities for LaTeX generation.
"""
import re


# Characters that must be escaped in LaTeX text content
_LATEX_ESCAPES = [
    ("\\", "\\textbackslash{}"),  # must be first
    ("&", "\\&"),
    ("%", "\\%"),
    ("$", "\\$"),
    ("#", "\\#"),
    ("_", "\\_"),
    ("{", "\\{"),
    ("}", "\\}"),
    ("~", "\\textasciitilde{}"),
    ("^", "\\textasciicircum{}"),
]

# Sequences we intentionally allow through (already valid LaTeX)
_PASSTHROUGH = re.compile(
    r"(\\textbf\{[^}]*\}|\\textit\{[^}]*\}|\\hrefWithoutArrow\{[^}]*\}\{[^}]*\}|\\item|\\&|\\%|\\\$|\\#|\\_|\\{|\\})"
)


def tex_escape(text: str) -> str:
    """
    Escape a plain-text string for use in LaTeX.
    Skips sequences that are already valid LaTeX commands.
    """
    if not text:
        return ""

    # Split on already-valid LaTeX sequences, escape everything else
    parts = _PASSTHROUGH.split(text)
    result = []
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Odd indices are the matched pass-through sequences
            result.append(part)
        else:
            for char, replacement in _LATEX_ESCAPES:
                part = part.replace(char, replacement)
            result.append(part)
    return "".join(result)


def sanitize_filename(name: str) -> str:
    """Turn a company name into a safe filename segment."""
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_")
