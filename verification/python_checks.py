"""Independent Python verification — hard rejects."""
import re
from typing import List

from data import get_line_snapshot
from schemas import Check, ProductionIssueReport

# Only flag numbers that are EXPLICITLY framed as metric citations:
# "62%", "78 min", "20 minutes", "3.1 percent". Bare numbers (station 4, PWO-1002,
# timestamps, incident-detail counts) are not metric citations and are skipped.
_METRIC_RE = re.compile(
    r"(-?\d+(?:\.\d+)?)\s*(?:%|percent\b|min(?:ute)?s?\b)",
    re.IGNORECASE,
)


def _all_numeric_grounds(line_id: str) -> List[float]:
    """Numeric values from the line snapshot that evidence may legitimately cite."""
    snap = get_line_snapshot(line_id)
    grounds: List[float] = []
    for d in (snap["current_metrics"], snap["kpi_baselines"]):
        for v in d.values():
            try:
                grounds.append(float(v))
            except (TypeError, ValueError):
                pass
    grounds.append(float(snap["safety_incidents_this_week"]))
    # Also include any numeric tokens found in incident descriptions, e.g. "cleared after 22 min".
    for inc in snap.get("recent_incidents", []):
        for m in re.findall(r"-?\d+(?:\.\d+)?", inc.get("description", "")):
            try:
                grounds.append(float(m))
            except ValueError:
                pass
    return grounds


def _close(a: float, grounds: List[float], tol: float = 0.15) -> bool:
    return any(abs(a - g) <= tol for g in grounds)


def run_python_checks(report: ProductionIssueReport, line_id: str, standards: List[dict]) -> List[Check]:
    checks: List[Check] = []
    standard_ids = {s["id"] for s in standards}
    grounds = _all_numeric_grounds(line_id)

    # 1. Standard ID existence
    bad_std = [h.standard_id for h in report.hypotheses if h.standard_id not in standard_ids]
    checks.append(Check(
        name="standard_id_existence",
        result="FAIL" if bad_std else "PASS",
        notes=f"Unknown standard_ids: {bad_std}" if bad_std else "All standard_ids resolve.",
    ))

    # 2. Hypothesis rank reference
    ranks = {h.rank for h in report.hypotheses}
    bad_links = [a.linked_hypothesis_rank for a in report.actions if a.linked_hypothesis_rank not in ranks]
    checks.append(Check(
        name="hypothesis_rank_reference",
        result="FAIL" if bad_links else "PASS",
        notes=f"Actions link to nonexistent hypothesis ranks: {bad_links}" if bad_links else "All actions link to real hypotheses.",
    ))

    # 3. Evidence numeric grounding — only check numbers framed as metric citations
    ungrounded = []
    for h in report.hypotheses:
        nums = [float(m) for m in _METRIC_RE.findall(h.evidence)]
        for n in nums:
            if not _close(n, grounds):
                ungrounded.append((h.rank, n))
    checks.append(Check(
        name="evidence_numeric_grounding",
        result="FAIL" if ungrounded else "PASS",
        notes=f"Numbers in evidence not found in line data (rank, value): {ungrounded}" if ungrounded else "All numeric evidence values resolve to known metrics or baselines.",
    ))

    # 4. Hypothesis count bounds
    n_hyp = len(report.hypotheses)
    checks.append(Check(
        name="hypothesis_count_bounds",
        result="PASS" if 2 <= n_hyp <= 4 else "FAIL",
        notes=f"Hypothesis count = {n_hyp} (expected 2-4).",
    ))

    # 5. Action count bounds
    n_act = len(report.actions)
    checks.append(Check(
        name="action_count_bounds",
        result="PASS" if 3 <= n_act <= 6 else "FAIL",
        notes=f"Action count = {n_act} (expected 3-6).",
    ))

    # 6. Stabilize bucket coverage
    has_stabilize = any(a.bucket == "Stabilize" for a in report.actions)
    checks.append(Check(
        name="stabilize_bucket_coverage",
        result="PASS" if has_stabilize else "FAIL",
        notes="At least one Stabilize action present." if has_stabilize else "No Stabilize action — operations manager has no immediate next step.",
    ))

    return checks
