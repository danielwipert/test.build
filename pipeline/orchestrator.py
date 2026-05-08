"""Pipeline orchestrator with closed-loop retry and graceful degradation."""
from datetime import datetime
from typing import Any, Dict, List

from data import load_standards
from pipeline.generation import run_generation
from pipeline.triage import run_triage
from pipeline.verification import run_verification
from schemas import Check, ProductionIssueReport, VerificationResult
from verification.python_checks import run_python_checks


def _failed_check_notes(checks: List[Check]) -> List[str]:
    return [f"[{c.name}] {c.notes}" for c in checks if c.result == "FAIL"]


def _apply_confidence_adjustments(report: ProductionIssueReport, vr: VerificationResult) -> None:
    by_rank = {h.rank: h for h in report.hypotheses}
    for adj in vr.confidence_adjustments:
        h = by_rank.get(adj.hypothesis_rank)
        if h is not None:
            h.confidence = adj.adjusted


def run_pipeline(
    problem_statement: str,
    line_id: str,
    timestamp: datetime,
    notes: str = "",
) -> Dict[str, Any]:
    failure_reasons: List[str] = []
    retry_count = 0
    standards = load_standards()
    attempts: List[Dict[str, Any]] = []

    triage = run_triage(problem_statement, line_id, timestamp, notes)

    # First Stage-2 attempt
    report = run_generation(triage, line_id, standards)
    py_checks = run_python_checks(report, line_id, standards)
    attempts.append({"report": report.model_dump(mode="json"), "python_checks": [c.model_dump() for c in py_checks]})

    # Retry on hard Python-check failure
    if any(c.result == "FAIL" for c in py_checks):
        feedback = "Python checks failed:\n- " + "\n- ".join(_failed_check_notes(py_checks))
        failure_reasons.append("python_checks_first_attempt: " + "; ".join(_failed_check_notes(py_checks)))
        retry_count += 1
        report = run_generation(triage, line_id, standards, feedback=feedback)
        py_checks = run_python_checks(report, line_id, standards)
        attempts.append({"report": report.model_dump(mode="json"), "python_checks": [c.model_dump() for c in py_checks]})

    # LLM verification
    vr = run_verification(triage, report, standards, py_checks)

    # Retry once on Stage-3 critical FAIL (only if we haven't already retried)
    if vr.status == "FAIL" and retry_count == 0:
        feedback = (
            "Stage 3 verifier returned FAIL. Notes: " + vr.overall_notes + "\n"
            + "Failed checks:\n- " + "\n- ".join(f"[{c.name}] {c.notes}" for c in vr.checks if c.result == "FAIL")
        )
        failure_reasons.append("stage3_first_attempt: " + vr.overall_notes)
        retry_count += 1
        report = run_generation(triage, line_id, standards, feedback=feedback)
        py_checks = run_python_checks(report, line_id, standards)
        attempts.append({"report": report.model_dump(mode="json"), "python_checks": [c.model_dump() for c in py_checks]})
        vr = run_verification(triage, report, standards, py_checks)

    # Apply confidence adjustments (mutates report in-place)
    _apply_confidence_adjustments(report, vr)

    py_failed = any(c.result == "FAIL" for c in py_checks)
    unverified = py_failed or vr.status == "FAIL"
    if py_failed:
        failure_reasons.append("python_checks_final: " + "; ".join(_failed_check_notes(py_checks)))
    if vr.status == "FAIL":
        failure_reasons.append("stage3_final: " + vr.overall_notes)

    return {
        "triage": triage,
        "report": report,
        "python_checks": py_checks,
        "verification": vr,
        "unverified": unverified,
        "retry_count": retry_count,
        "failure_reasons": failure_reasons,
        "attempts": attempts,
    }
