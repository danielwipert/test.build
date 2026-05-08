"""Stage 1 — Triage."""
import json
import os
from datetime import datetime

from data import get_line_snapshot
from llm_client import MODEL_TRIAGE, call_llm
from schemas import TriageOutput

_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "triage.txt")


def _load_prompt() -> str:
    with open(_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


def run_triage(problem_statement: str, line_id: str, timestamp: datetime, notes: str = "") -> TriageOutput:
    snapshot = get_line_snapshot(line_id)
    user = (
        f"PROBLEM STATEMENT:\n{problem_statement}\n\n"
        f"INCIDENT TIMESTAMP: {timestamp.isoformat()}\n\n"
        f"LINE SNAPSHOT:\n{json.dumps(snapshot, indent=2, default=str)}\n\n"
        f"MANAGER NOTES: {notes or '(none)'}\n"
    )
    return call_llm(MODEL_TRIAGE, _load_prompt(), user, TriageOutput)
