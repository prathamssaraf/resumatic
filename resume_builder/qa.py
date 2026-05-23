"""
QA checks on the assembled .tex before compilation.
Every locked metric must appear verbatim.
70/30 rule is estimated and reported.
"""
from __future__ import annotations
import re
from graph import queries
from .utils import tex_escape


def run(tex: str, selected_project_ids: list[str]) -> dict:
    """
    Returns:
      {
        "passed": bool,
        "metric_checks": [{"metric": str, "value": str, "found": bool}, ...],
        "missing_metrics": [str, ...],
        "keyword_ratio_ok": bool,
        "warnings": [str, ...]
      }
    """
    all_metrics = queries.get_all_metrics()
    warnings: list[str] = []
    metric_checks: list[dict] = []
    missing: list[str] = []

    # Determine which metrics are relevant to this resume
    # (experience metrics always included; project metrics only if project selected)
    project_metric_ids: set[str] = set()
    for pid in selected_project_ids:
        proj = queries.get_project_with_metrics(pid)
        if proj:
            for m in proj.get("metrics", []):
                project_metric_ids.add(f"{proj['name']}:{m['label']}")

    for m in all_metrics:
        # Always check experience + education metrics
        is_exp = m["source"] in ("HPE", "ONGC", "OnFees", "NYU")
        # Only check project metrics if that project is in the resume
        is_proj = any(
            m["source"] == p_name
            for p_name in [queries.get_project_with_metrics(pid)["name"] for pid in selected_project_ids if queries.get_project_with_metrics(pid)]
        )

        if not (is_exp or is_proj):
            continue

        # Check both raw value and tex-escaped value (% → \%, etc.)
        found = m["value"] in tex or tex_escape(m["value"]) in tex
        metric_checks.append({
            "metric": f"{m['source']} — {m['label']}",
            "value": m["value"],
            "found": found,
        })
        if not found:
            missing.append(f"{m['source']} — {m['label']}: {m['value']}")

    # Rough 70/30 check: count distinct keywords that appear 3+ times
    # (proxy for over-stuffing)
    word_freq = {}
    for word in re.findall(r"\b[a-zA-Z]{4,}\b", tex):
        word_freq[word.lower()] = word_freq.get(word.lower(), 0) + 1
    repeated_keywords = [w for w, c in word_freq.items() if c >= 5 and len(w) > 4]
    if len(repeated_keywords) > 20:
        warnings.append(
            f"Possible keyword stuffing: {len(repeated_keywords)} words appear 5+ times. "
            "Check 70/30 rule."
        )

    passed = len(missing) == 0

    return {
        "passed": passed,
        "metric_checks": metric_checks,
        "missing_metrics": missing,
        "warnings": warnings,
    }


def report(qa_result: dict) -> str:
    lines = []
    lines.append("\n── QA REPORT ──────────────────────────────")
    status = "✓ PASSED" if qa_result["passed"] else "✗ FAILED"
    lines.append(f"Status: {status}")
    lines.append(f"\nMetric checks ({len(qa_result['metric_checks'])} total):")
    for check in qa_result["metric_checks"]:
        icon = "✓" if check["found"] else "✗"
        lines.append(f"  {icon} {check['metric']}: {check['value']}")
    if qa_result["missing_metrics"]:
        lines.append("\nMISSING METRICS (must be fixed):")
        for m in qa_result["missing_metrics"]:
            lines.append(f"  ✗ {m}")
    if qa_result["warnings"]:
        lines.append("\nWarnings:")
        for w in qa_result["warnings"]:
            lines.append(f"  ⚠ {w}")
    lines.append("────────────────────────────────────────────\n")
    return "\n".join(lines)
