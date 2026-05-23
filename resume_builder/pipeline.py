"""
Main pipeline orchestrator.
Runs all 6 steps in order and returns a result dict.
"""
from __future__ import annotations
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from . import selector as sel
from .sections import header, education, experience, projects, skills, extra
from . import assembler, qa, compiler, cover_letter, page_checker

console = Console()


def run_pipeline(
    jd_text: str,
    *,
    compile_pdf: bool = True,
    generate_cover: bool = True,
) -> dict:
    """
    Full pipeline from JD text to .tex + .pdf.
    Returns a result dict with paths, QA report, and analysis.
    """
    result: dict = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:

        # ── Step 0: Analyse JD ───────────────────────────────────────────────
        task = progress.add_task("Step 0 — Analysing job description...", total=None)
        jd_analysis = sel.analyse_jd(jd_text)
        result["jd_analysis"] = jd_analysis

        company = jd_analysis.get("company_name", "Company")
        role = jd_analysis.get("role_type", "role_fullstack")
        red_flags = jd_analysis.get("red_flags", [])
        progress.update(task, description=f"✓ Step 0 — {company} | {role} | flags: {red_flags or 'none'}")

        if "itar" in red_flags:
            console.print("[bold red]✗ AUTOMATIC REJECT: ITAR restriction detected.[/bold red]")
            return {"error": "itar", "jd_analysis": jd_analysis}
        if "clearance" in red_flags:
            console.print("[bold red]✗ AUTOMATIC REJECT: Security clearance required.[/bold red]")
            return {"error": "clearance", "jd_analysis": jd_analysis}
        if "no_visa" in red_flags:
            console.print("[bold yellow]⚠ WARNING: No visa sponsorship stated. Proceeding anyway.[/bold yellow]")

        # ── Step 1: Selection ────────────────────────────────────────────────
        progress.update(task, description="Step 1 — Selecting projects and titles...")
        selection = sel.select(jd_analysis)
        result["selection"] = selection
        progress.update(
            task,
            description=f"✓ Step 1 — Projects: {selection.get('selected_project_ids')} | HPE: {selection.get('hpe_title')}",
        )

        # ── Step 2a: Education ───────────────────────────────────────────────
        progress.update(task, description="Step 2a — Generating education section...")
        edu_tex = education.render(jd_analysis, selection)

        # ── Step 2b: Experience ──────────────────────────────────────────────
        progress.update(task, description="Step 2b — Generating experience bullets (3 K2 calls)...")
        exp_tex = experience.render(jd_analysis, selection)

        # ── Step 2c: Projects ────────────────────────────────────────────────
        progress.update(task, description="Step 2c — Generating project descriptions...")
        proj_tex = projects.render(jd_analysis, selection)

        # ── Step 2d: Skills ──────────────────────────────────────────────────
        progress.update(task, description="Step 2d — Building skills section...")
        skills_tex = skills.render(jd_analysis, selection)

        # ── Static sections ──────────────────────────────────────────────────
        header_tex = header.render()
        extra_tex = extra.render()

        # ── Step 3: Assemble ─────────────────────────────────────────────────
        progress.update(task, description="Step 3 — Assembling .tex file...")
        tex_body, tex_path = assembler.assemble_resume(
            company,
            header_tex,
            edu_tex,
            exp_tex,
            proj_tex,
            skills_tex,
            extra_tex,
        )
        result["tex_path"] = str(tex_path)
        progress.update(task, description=f"✓ Step 3 — Written: {tex_path.name}")

        # ── Step 4: QA ───────────────────────────────────────────────────────
        progress.update(task, description="Step 4 — Running QA checks...")
        qa_result = qa.run(tex_body, selection.get("selected_project_ids", []))
        result["qa"] = qa_result
        qa_status = "✓ PASSED" if qa_result["passed"] else "✗ FAILED"
        progress.update(task, description=f"Step 4 — QA {qa_status}")

        # ── Cover letter ─────────────────────────────────────────────────────
        if generate_cover:
            progress.update(task, description="Generating cover letter (1 K2 call)...")
            paragraphs = cover_letter.generate(jd_analysis, selection)
            _, cl_path = assembler.assemble_cover_letter(company, jd_analysis, paragraphs)
            result["cover_letter_tex_path"] = str(cl_path)
            progress.update(task, description=f"✓ Cover letter — {cl_path.name}")

        # ── Step 5: Compile ──────────────────────────────────────────────────
        if compile_pdf:
            progress.update(task, description="Step 5 — Compiling resume PDF...")
            success, log = compiler.compile(tex_path)
            result["pdf_compiled"] = success
            result["compile_log"] = log
            if success:
                result["pdf_path"] = log
                progress.update(task, description=f"✓ Step 5 — PDF: {Path(log).name}")

                # Step 5b: page check — compress if > 1 page
                pdf_path = Path(log)
                pages = page_checker.count_pages(pdf_path)
                if pages > 1:
                    progress.update(task, description=f"Step 5b — Resume is {pages} page(s), compressing...")
                    fits = page_checker.check_and_fix(tex_path, pdf_path)
                    result["page_check"] = "1 page" if fits else f"{pages} pages (compression attempted)"
                    progress.update(task, description="✓ Step 5b — Page check done")
                else:
                    result["page_check"] = "1 page"
            else:
                progress.update(task, description="✗ Step 5 — Compile failed (see compile_log)")

            if generate_cover:
                cl_path_obj = Path(result["cover_letter_tex_path"])
                progress.update(task, description="Compiling cover letter PDF...")
                cl_success, cl_log = compiler.compile(cl_path_obj, runs=1)
                result["cover_pdf_compiled"] = cl_success
                if cl_success:
                    result["cover_pdf_path"] = cl_log

        progress.update(task, description="Done.")

    # Print summary
    _print_summary(result, jd_analysis, selection, qa_result)
    return result


def _print_summary(result: dict, jd: dict, sel_data: dict, qa_result: dict) -> None:
    console.print(f"\n[bold cyan]── Resume Builder Summary ────────────────────[/bold cyan]")
    console.print(f"  Company:        {jd.get('company_name')}")
    console.print(f"  Position:       {jd.get('position_title')}")
    console.print(f"  Role type:      {jd.get('role_type')}")
    console.print(f"  Match (before): {jd.get('match_percent_before')}%")
    console.print(f"  Red flags:      {jd.get('red_flags') or 'none'}")
    console.print(f"\n  Projects selected: {sel_data.get('selected_project_ids')}")
    console.print(f"  HPE title:         {sel_data.get('hpe_title')}")
    console.print(f"  ONGC title:        {sel_data.get('ongc_title')}")
    console.print(f"  Skills added:      {[s['name'] for s in sel_data.get('skills_to_add', [])]}")

    console.print(f"\n  Resume .tex:    {result.get('tex_path', 'n/a')}")
    if result.get("pdf_path"):
        console.print(f"  Resume .pdf:    {result.get('pdf_path')}")
        if result.get("page_check"):
            color = "green" if result["page_check"] == "1 page" else "yellow"
            console.print(f"  Pages:          [{color}]{result['page_check']}[/{color}]")
    if result.get("cover_letter_tex_path"):
        console.print(f"  Cover letter:   {result.get('cover_letter_tex_path')}")

    qa_color = "green" if qa_result["passed"] else "red"
    console.print(f"\n  QA:  [{qa_color}]{('✓ PASSED' if qa_result['passed'] else '✗ FAILED')}[/{qa_color}]")
    if qa_result["missing_metrics"]:
        for m in qa_result["missing_metrics"]:
            console.print(f"    [red]✗ Missing metric: {m}[/red]")
    if qa_result.get("warnings"):
        for w in qa_result["warnings"]:
            console.print(f"    [yellow]⚠ {w}[/yellow]")

    console.print("[bold cyan]──────────────────────────────────────────────[/bold cyan]\n")
