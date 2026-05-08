"""Stage 2 — Generation."""
import json
import os
from typing import List, Optional

from data import get_line_snapshot
from llm_client import MODEL_GENERATION, call_llm
from schemas import ProductionIssueReport, TriageOutput

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "generation.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run_generation(
    triage: TriageOutput,
    line_id: str,
    standards: List[dict],
    feedback: Optional[str] = None,
) -> ProductionIssueReport:
    snapshot = get_line_snapshot(line_id)
    user = (
        f"TRIAGE OUTPUT:\n{triage.model_dump_json(indent=2)}\n\n"
        f"LINE SNAPSHOT:\n{json.dumps(snapshot, indent=2, default=str)}\n\n"
        f"PROCESS STANDARDS:\n{json.dumps(standards, indent=2)}\n\n"
    )
    if feedback:
        user += f"PRIOR-ATTEMPT FEEDBACK (address every point):\n{feedback}\n"
    return call_llm(MODEL_GENERATION, _load_prompt(), user, ProductionIssueReport)
