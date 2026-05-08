"""Stage 3 — LLM verification."""
import json
import os
from typing import List

from llm_client import MODEL_VERIFICATION, call_llm
from schemas import Check, ProductionIssueReport, TriageOutput, VerificationResult

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "verification.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run_verification(
    triage: TriageOutput,
    report: ProductionIssueReport,
    standards: List[dict],
    python_checks: List[Check],
) -> VerificationResult:
    user = (
        f"TRIAGE OUTPUT:\n{triage.model_dump_json(indent=2)}\n\n"
        f"PROCESS STANDARDS:\n{json.dumps(standards, indent=2)}\n\n"
        f"REPORT UNDER REVIEW:\n{report.model_dump_json(indent=2)}\n\n"
        f"PYTHON CHECKS ALREADY RUN:\n{json.dumps([c.model_dump() for c in python_checks], indent=2)}\n"
    )
    return call_llm(MODEL_VERIFICATION, _load_prompt(), user, VerificationResult)
