"""
XeLaTeX compilation.
Tries common install locations on macOS.
"""
from __future__ import annotations
import subprocess
import shutil
from pathlib import Path


XELATEX_CANDIDATES = [
    "/Library/TeX/texbin/xelatex",
    "/usr/local/texlive/2026/bin/universal-apple/xelatex",
    "/usr/local/texlive/2025/bin/universal-apple/xelatex",
    "/usr/local/texlive/2024/bin/universal-apple/xelatex",
    "/usr/local/bin/xelatex",
    "xelatex",  # on PATH
]


def _find_xelatex() -> str | None:
    for candidate in XELATEX_CANDIDATES:
        if shutil.which(candidate) or Path(candidate).exists():
            return candidate
    return None


def compile(tex_path: Path, *, runs: int = 2) -> tuple[bool, str]:
    """
    Compile a .tex file with xelatex.
    Returns (success, log_excerpt).
    Runs twice by default for proper cross-references.
    """
    xelatex = _find_xelatex()
    if not xelatex:
        return False, (
            "xelatex not found. Install MacTeX: brew install --cask mactex-no-gui\n"
            "Then ensure /Library/TeX/texbin is on your PATH."
        )

    tex_path = Path(tex_path).resolve()  # absolute path avoids cwd confusion
    output_dir = tex_path.parent

    log_output = ""
    for _ in range(runs):
        result = subprocess.run(
            [
                xelatex,
                "-interaction=nonstopmode",
                "-halt-on-error",
                f"-output-directory={output_dir}",
                str(tex_path),
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        log_output = result.stdout + result.stderr

    pdf_path = tex_path.with_suffix(".pdf")
    success = pdf_path.exists() and pdf_path.stat().st_size > 1000

    if not success:
        # Extract the most useful error lines
        error_lines = [
            line for line in log_output.splitlines()
            if line.startswith("!") or "Error" in line or "error" in line
        ]
        return False, "\n".join(error_lines[:20])

    return True, str(pdf_path)
