"""
Post-compilation page checker.

Flow:
  1. Count pages. If 1, done.
  2. Get page-2 text. If ONLY extracurricular overflowed, strip that section and recompile.
  3. Otherwise ask Gemma for a ranked list of changes (removals/shortenings).
     Apply changes ONE AT A TIME — recompile and check after each.
     Stop the moment the resume fits on 1 page.
  4. Repeat up to max_attempts full Gemma rounds if needed.
"""
from __future__ import annotations
import re
import subprocess
from pathlib import Path
from rich.console import Console

from . import llm

console = Console()

_PDFINFO   = "/opt/homebrew/bin/pdfinfo"
_PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

# Keywords that indicate extracurricular-only overflow
_EXTRACURRICULAR_KEYWORDS = re.compile(
    r"extracurricular|hackathon|volunteer|mentor|club|society|activity|activities",
    re.I,
)
_NON_EXTRACURRICULAR_KEYWORDS = re.compile(
    r"experience|engineer|develop|project|skill|education|university|intern",
    re.I,
)

_COMPRESS_SYSTEM = """You are fixing a resume that overflows onto page 2.

CRITICAL INSIGHT — how to save vertical space:
  A) REMOVE a bullet entirely → saves exactly 1 line
  B) Shorten a bullet that WRAPS to 2 lines (>137 chars) to ≤137 chars → saves 1 line
  Shortening a single-line bullet (≤137 chars) saves ZERO lines.

You will receive a numbered bullet list. Each bullet shows its char count.
Return a RANKED list of changes — most impactful / least harmful first.
They will be applied one at a time until the resume fits, so order matters.

STRATEGY (rank in this order):
1. Shorten wrapping bullets (>137 chars) — least harmful way to save a line.
2. Remove the weakest single-line bullets (generic soft-skill bullets, duplicates).
3. Only as last resort: remove bullets with real content.

RULES:
- NEVER remove the only bullet in a highlights block (would leave it empty).
- NEVER remove a bullet that is the sole carrier of a locked metric value
  (numbers like "96.8%", "2M+", "95%", "25%", etc.).
- Never shorten below 70 characters.
- Preserve strong action verbs and quantified achievements.

Output JSON:
{
  "changes": [
    {"id": <number>, "original": "<exact bullet text>", "replacement": "<shorter text or null to remove>"},
    ...
  ]
}"""


def count_pages(pdf_path: Path) -> int:
    """Return page count. Falls back to 1 on any error."""
    try:
        r = subprocess.run([_PDFINFO, str(pdf_path)],
                           capture_output=True, text=True, timeout=10)
        m = re.search(r"Pages:\s+(\d+)", r.stdout)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    log = pdf_path.with_suffix(".log")
    if log.exists():
        text = log.read_text(errors="ignore").replace("\n", " ")
        m = re.search(r"Output written on[^(]+\((\d+) page", text)
        if m:
            return int(m.group(1))
    return 1


def _page2_text(pdf_path: Path) -> str:
    """Return the text content of page 2 (empty string if only 1 page)."""
    try:
        r = subprocess.run(
            [_PDFTOTEXT, "-f", "2", "-l", "2", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout
    except Exception:
        return ""


def _overflow_lines(page2: str) -> int:
    """Count non-empty lines on page 2."""
    non_empty = [l for l in page2.splitlines() if l.strip()]
    return max(2, len(non_empty))


def _is_only_extracurricular(page2: str) -> bool:
    """True if page 2 contains only extracurricular content — nothing substantive."""
    if not page2.strip():
        return False
    has_extra = bool(_EXTRACURRICULAR_KEYWORDS.search(page2))
    has_real  = bool(_NON_EXTRACURRICULAR_KEYWORDS.search(page2))
    return has_extra and not has_real


def _remove_extracurricular(tex: str) -> str:
    """Strip the entire Extracurricular Activities section from the tex."""
    # Remove \section{Extracurricular...} through the end of its content block
    tex = re.sub(
        r"\s*\\section\{[^}]*(?:Extracurricular|Activities)[^}]*\}.*?(?=\\section\{|\\end\{document\})",
        "\n",
        tex,
        flags=re.DOTALL | re.I,
    )
    return tex


def _extract_bullets(tex: str) -> list[str]:
    return re.findall(r"\\item (.+)", tex)


def _bullets_per_block(tex: str) -> dict[str, int]:
    """Map each bullet text → how many bullets share its highlights block."""
    counts: dict[str, int] = {}
    for block in re.findall(r"\\begin\{highlights\}(.*?)\\end\{highlights\}", tex, re.DOTALL):
        items = re.findall(r"\\item (.+)", block)
        for it in items:
            counts[it] = len(items)
    return counts


def _clean_empty_blocks(tex: str) -> str:
    """Remove project title entries whose highlights block is now empty."""
    tex = re.sub(
        r"\s*\\begin\{onecolentry\}\s*\\textbf\{[^}]*(?:\{[^}]*\}[^}]*)?\}[^\n]*\n\s*\\end\{onecolentry\}"
        r"\s*\\vspace\{[^}]+\}\s*"
        r"\\begin\{onecolentry\}\s*\\begin\{highlights\}\s*\\end\{highlights\}\s*\\end\{onecolentry\}"
        r"(\s*\\vspace\{[^}]+\})?",
        "",
        tex,
    )
    tex = re.sub(
        r"\s*\\section\{[^}]+\}\s*"
        r"\\begin\{onecolentry\}\s*\\begin\{highlightsforbulletentries\}\s*"
        r"\\end\{highlightsforbulletentries\}\s*\\end\{onecolentry\}",
        "",
        tex,
    )
    return tex


def _apply_one(tex: str, change: dict) -> str:
    """Apply a single change dict to the tex string."""
    original    = change.get("original", "")
    replacement = change.get("replacement")
    if not original:
        return tex
    if replacement is None:
        tex = re.sub(
            r"[ \t]*\\item " + re.escape(original) + r"[ \t]*\n?",
            "",
            tex,
        )
    else:
        tex = tex.replace(f"\\item {original}", f"\\item {replacement}", 1)
    return tex


def check_and_fix(tex_path: Path, pdf_path: Path, *, max_attempts: int = 2) -> bool:
    """
    Check page count. If > 1 page:
      - Extracurricular-only overflow → strip section, done.
      - Otherwise ask Gemma for ranked changes, apply one at a time.
    Returns True if final PDF is 1 page.
    """
    from .compiler import compile as xelatex_compile

    if count_pages(pdf_path) <= 1:
        return True

    for attempt in range(1, max_attempts + 1):
        p2 = _page2_text(pdf_path)
        lines_over = _overflow_lines(p2)

        console.print(
            f"  [yellow]⚠ Page 2 overflow (~{lines_over} lines). "
            f"Attempt {attempt}/{max_attempts}[/yellow]"
        )

        # ── Fast path: only extracurricular overflowed ─────────────────────
        if _is_only_extracurricular(p2):
            console.print("  Extracurricular-only overflow — stripping section...")
            tex = tex_path.read_text(encoding="utf-8")
            tex_path.write_text(_remove_extracurricular(tex), encoding="utf-8")
            ok, _ = xelatex_compile(tex_path)
            if ok and count_pages(pdf_path) <= 1:
                console.print("  [green]✓ 1 page after stripping extracurricular.[/green]")
                return True
            # fell through — section wasn't enough, continue to Gemma path

        # ── Gemma path: get ranked changes, apply one at a time ────────────
        tex     = tex_path.read_text(encoding="utf-8")
        bullets = _extract_bullets(tex)
        if not bullets:
            console.print("  [red]No bullets to compress.[/red]")
            return False

        block_counts = _bullets_per_block(tex)
        numbered = "\n".join(
            f"{i+1}. [{len(b)} chars"
            f"{'  ← WRAPS' if len(b) > 137 else ''}"
            f"{' — SOLE bullet in block, do not remove' if block_counts.get(b, 99) == 1 else ''}] {b}"
            for i, b in enumerate(bullets)
        )

        result  = llm.call_json(
            _COMPRESS_SYSTEM,
            f"RESUME BULLETS ({len(bullets)} total):\n{numbered}\n\n"
            f"The resume overflows by ~{lines_over} lines. "
            f"Return a RANKED list of changes. They will be applied one at a time "
            f"and we stop as soon as the resume fits — so put the safest/most impactful first.",
        )
        changes = result.get("changes", []) if isinstance(result, dict) else []

        if not changes:
            console.print("  [red]Gemma returned no changes.[/red]")
            return False

        console.print(f"  Got {len(changes)} ranked change(s) — applying one at a time...")

        for i, change in enumerate(changes, 1):
            current_tex = tex_path.read_text(encoding="utf-8")
            new_tex     = _apply_one(current_tex, change)
            new_tex     = _clean_empty_blocks(new_tex)
            tex_path.write_text(new_tex, encoding="utf-8")

            ok, _ = xelatex_compile(tex_path)
            if not ok:
                # Restore this step and skip to next change
                tex_path.write_text(current_tex, encoding="utf-8")
                continue

            if count_pages(pdf_path) <= 1:
                console.print(f"  [green]✓ 1 page after {i} change(s).[/green]")
                return True

        console.print(f"  Still > 1 page after all {len(changes)} changes.")

    console.print(f"  [red]Could not compress to 1 page after {max_attempts} attempt(s).[/red]")
    return False
