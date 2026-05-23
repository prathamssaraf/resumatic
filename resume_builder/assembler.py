"""
Assembles all rendered sections into a complete .tex file.
Also handles cover letter assembly.
"""
from __future__ import annotations
from pathlib import Path
from datetime import date
from .framework import PREAMBLE, DOCUMENT_OPEN, DOCUMENT_CLOSE, COVER_PREAMBLE
from .utils import tex_escape, sanitize_filename


OUTPUT_DIR       = Path(__file__).parent.parent / "output"
RESUME_DIR       = OUTPUT_DIR / "resumes"
COVER_LETTER_DIR = OUTPUT_DIR / "cover_letters"


def assemble_resume(
    company_name: str,
    header: str,
    education: str,
    experience: str,
    projects: str,
    skills: str,
    extra: str,
) -> tuple[str, Path]:
    """
    Combine all sections into a complete .tex document.
    Returns (tex_content, output_path).
    """
    RESUME_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(company_name)
    tex_path = RESUME_DIR / f"Pratham_Saraf_Resume_{safe_name}.tex"

    body = (
        PREAMBLE
        + DOCUMENT_OPEN
        + header
        + education
        + experience
        + projects
        + skills
        + extra
        + DOCUMENT_CLOSE
    )

    tex_path.write_text(body, encoding="utf-8")
    return body, tex_path


def assemble_cover_letter(
    company_name: str,
    jd_analysis: dict,
    paragraphs: list[str],
) -> tuple[str, Path]:
    """
    Assemble a cover letter .tex file.
    Returns (tex_content, output_path).
    """
    COVER_LETTER_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = sanitize_filename(company_name)
    tex_path = COVER_LETTER_DIR / f"Pratham_Saraf_CoverLetter_{safe_name}.tex"

    today = date.today().strftime("%B %d, %Y")
    position = tex_escape(jd_analysis.get("position_title", "Software Engineer"))
    company = tex_escape(company_name)

    para_tex = "\n\n".join(f"\\noindent\n{tex_escape(p)}" for p in paragraphs)

    body = (
        COVER_PREAMBLE
        + r"""
\begin{document}

\noindent
\textbf{\Large Pratham Saraf} \\
Brooklyn, New York, USA \\
ps5218@nyu.edu | +1 347-793-7420 \\
github.com/prathamssaraf

\vspace{0.5cm}

\noindent
"""
        + today
        + r"""

\vspace{0.3cm}

\noindent
Hiring Manager \\
"""
        + company
        + r"""

\vspace{0.3cm}

\noindent
Dear Hiring Manager,

"""
        + para_tex
        + r"""

\vspace{0.3cm}

\noindent
Sincerely, \\
Pratham Saraf

\end{document}"""
    )

    tex_path.write_text(body, encoding="utf-8")
    return body, tex_path
