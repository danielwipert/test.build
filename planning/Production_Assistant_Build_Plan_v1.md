# Production Issue Resolution Assistant — Build Plan v1

**Companion to:** `Production_Assistant_Spec_v1.md`
**Document type:** Temporal build artifact (block-by-block, with done-when criteria)
**Build environment:** Claude Code, Windows terminal, Python
**Target build window:** 60–90 minutes

---

## Pre-flight (do this first, ~2 minutes)

- [ ] Confirm Together AI API key is in environment (`TOGETHER_API_KEY`)
- [ ] Confirm Python 3.10+ available
- [ ] Create project folder: `production-assistant/`
- [ ] Open Claude Code in that folder

**Done when:** terminal is open in `production-assistant/` with API key accessible.

---

## Block 1 — Scaffolding (~5 minutes)

**Goal:** Project skeleton with dependencies installed and a `CLAUDE.md` for Claude Code continuity.

### Tasks
- [ ] Create folder structure:
  ```
  production-assistant/
  ├── app.py                  (Streamlit entry point — written last)
  ├── pipeline/
  │   ├── __init__.py
  │   ├── triage.py           (Stage 1)
  │   ├── generation.py       (Stage 2)
  │   ├── verification.py     (Stage 3 LLM verifier)
  │   └── orchestrator.py     (runs the pipeline, handles retry)
  ├── verification/
  │   ├── __init__.py
  │   └── python_checks.py    (independent factual verification)
  ├── schemas.py              (all Pydantic models)
  ├── data.py                 (synthetic factory data)
  ├── standards.json          (process standards)
  ├── llm_client.py           (Together AI wrapper)
  ├── prompts/
  │   ├── triage.txt
  │   ├── generation.txt
  │   └── verification.txt
  ├── requirements.txt
  ├── CLAUDE.md               (handoff doc for Claude Code)
  └── .env                    (gitignored)
  ```
- [ ] Write `requirements.txt`:
  ```
  streamlit
  pydantic
  python-dotenv
  requests
  ```
- [ ] Install: `pip install -r requirements.txt`
- [ ] Write a minimal `CLAUDE.md` referencing the spec and decisions log

**Done when:** folder structure exists, dependencies installed, `streamlit hello` runs successfully as a smoke test.

---

## Block 2 — Synthetic data + standards (~8 minutes)

**Goal:** All reference data exists and is loadable.

### Tasks
- [ ] Write `data.py` with:
  - `FACTORIES` dict: `{"FAC-01": {...}}`
  - `LINES` dict: 3 lines with `current_metrics`, `kpi_baselines`, `safety_incidents_this_week`
  - `INCIDENT_LOG`: list of 3 dicts, each with `timestamp`, `line_id`, `description`
  - `PWOS`: dict of 3 PWOs with expected vs. actual start times
  - Helper function `get_line_snapshot(line_id) -> dict` that returns everything about a line
- [ ] Write `standards.json` with 6–8 standards covering:
  - `STD-001`: Throughput baseline thresholds
  - `STD-002`: Defect rate response protocol
  - `STD-003`: Supplier delay escalation
  - `STD-004`: Safety incident reporting
  - `STD-005`: Equipment downtime triage
  - `STD-006`: Quality threshold variance protocol
  - (optional) `STD-007`, `STD-008`: maintenance and PWO timing
- [ ] Write helper `load_standards() -> List[dict]` (in `data.py` or its own file)

### Sanity check
- [ ] `python -c "from data import get_line_snapshot; print(get_line_snapshot('LINE-B2'))"` returns a dict
- [ ] `python -c "import json; print(len(json.load(open('standards.json'))))"` prints the standards count

**Done when:** synthetic data loads, standards load, both can be inspected from a Python REPL.

---

## Block 3 — Pydantic schemas (~5 minutes)

**Goal:** All schemas from Spec Section 6 implemented and importable.

### Tasks
- [ ] Write `schemas.py` with all classes from Spec Section 6:
  - `KPIBreach`, `TriageOutput`
  - `Hypothesis`, `ActionItem`, `ProductionIssueReport`
  - `Check`, `ConfidenceAdjustment`, `VerificationResult`
- [ ] Use `Literal` from `typing` for enum-like fields
- [ ] Use `datetime` for timestamps
- [ ] Add field validators where helpful (e.g., `rank >= 1`)

### Sanity check
- [ ] Build a minimal valid `ProductionIssueReport` by hand in a Python REPL — should validate without errors
- [ ] Build a deliberately invalid one (e.g., `rank=0`) — should raise `ValidationError`

**Done when:** all schemas import cleanly and round-trip valid/invalid example data correctly.

---

## Block 4 — LLM client (~7 minutes)

**Goal:** A single function that takes (model_name, system_prompt, user_prompt, response_schema) and returns a validated Pydantic object.

### Tasks
- [ ] Write `llm_client.py`:
  - Loads `TOGETHER_API_KEY` from environment
  - Function `call_llm(model: str, system: str, user: str, schema: Type[BaseModel]) -> BaseModel`
  - Uses Together AI's chat completions endpoint
  - Requests JSON-formatted output (set `response_format` if supported, otherwise instruct in system prompt)
  - Parses response, validates against `schema`, returns instance
  - On JSON parse error or validation error: one retry with the error appended to the prompt
  - On second failure: raise `LLMOutputError`
- [ ] Define model constants:
  ```python
  MODEL_TRIAGE = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
  MODEL_GENERATION = "deepseek-ai/DeepSeek-V3"
  MODEL_VERIFICATION = "Qwen/Qwen2.5-72B-Instruct-Turbo"
  MODEL_FALLBACK = "mistralai/Mixtral-8x22B-Instruct-v0.1"
  ```
  (verify exact Together AI model strings against current free-tier list)

### Sanity check
- [ ] Run a minimal test: call Llama 3.3 70B with a trivial prompt asking for a `KPIBreach` JSON. Confirm it returns a validated object.

**Done when:** `call_llm` works end-to-end against Together AI for at least one stage.

---

## Block 5 — Stage 1 (Triage) (~10 minutes)

**Goal:** Stage 1 takes raw input and produces a validated `TriageOutput`.

### Tasks
- [ ] Write `prompts/triage.txt` — system prompt for Stage 1:
  - Role: triage analyst for apparel manufacturing
  - Input format: problem statement, factory/line data, timestamp
  - Output format: strict JSON matching `TriageOutput`
  - Instructions: identify breached KPIs by comparing current values to baselines, classify into one of four categories, list affected entities
  - Tell it to be conservative — only mark KPIs as Critical if they're significantly out of band
- [ ] Write `pipeline/triage.py`:
  - Function `run_triage(problem_statement: str, line_id: str, timestamp: datetime, notes: str = "") -> TriageOutput`
  - Loads line snapshot from `data.py`
  - Constructs user prompt with all context
  - Calls `call_llm(MODEL_TRIAGE, system, user, TriageOutput)`
  - Returns validated `TriageOutput`

### Sanity check
- [ ] Run Stage 1 on a hardcoded throughput-drop scenario. Print the output. Confirm:
  - Category is `"throughput"`
  - At least one breached KPI with `metric == "throughput_pct"`
  - Affected entities include the line ID

**Done when:** Stage 1 produces a coherent, validated `TriageOutput` for at least one preset scenario.

---

## Block 6 — Stage 2 (Generation) (~12 minutes)

**Goal:** Stage 2 takes `TriageOutput` + standards and produces a validated `ProductionIssueReport`.

### Tasks
- [ ] Write `prompts/generation.txt`:
  - Role: senior production engineer
  - Input: `TriageOutput`, full line data, full standards list
  - Output: strict JSON matching `ProductionIssueReport`
  - Instructions: generate 2–4 ranked hypotheses (highest likelihood first), each with evidence citing real metric values from the input data and a `standard_id` from the standards list. Generate 3–6 actions across `Stabilize`/`Investigate`/`Prevent` buckets, each linked to a hypothesis rank. Write a 2–3 sentence explanation.
  - Concrete examples in the prompt of good vs. bad evidence (good: "throughput at 62% vs. baseline 88%"; bad: "throughput is low")
- [ ] Write `pipeline/generation.py`:
  - Function `run_generation(triage: TriageOutput, line_id: str, standards: List[dict], feedback: Optional[str] = None) -> ProductionIssueReport`
  - The `feedback` arg is for retry-with-verifier-feedback
  - Constructs user prompt with all inputs (and feedback if present)
  - Calls `call_llm(MODEL_GENERATION, system, user, ProductionIssueReport)`
  - Returns validated report

### Sanity check
- [ ] Run Stages 1+2 on the throughput-drop scenario. Print the report. Confirm:
  - 2–4 hypotheses, each with a `standard_id` that exists in `standards.json`
  - 3–6 actions, each with `linked_hypothesis_rank` matching a real hypothesis
  - Evidence strings reference real metric values

**Done when:** Stage 2 produces a coherent, validated report for at least one scenario.

---

## Block 7 — Python independent verification (~8 minutes)

**Goal:** Hard-reject layer that catches factual errors deterministically.

### Tasks
- [ ] Write `verification/python_checks.py` with function `run_python_checks(report: ProductionIssueReport, line_id: str, standards: List[dict]) -> List[Check]`
- [ ] Implement these checks:
  1. **Standard ID existence** — every `hypothesis.standard_id` must be in `standards.json`
  2. **Hypothesis rank reference** — every `action.linked_hypothesis_rank` must match a real `hypothesis.rank`
  3. **Evidence numeric grounding** — for each hypothesis, extract numbers from the `evidence` string (regex for floats); confirm each appears in either `current_metrics` or `kpi_baselines` for the line (allow ±0.1 tolerance for rounding)
  4. **Hypothesis count bounds** — 2 ≤ count ≤ 4
  5. **Action count bounds** — 3 ≤ count ≤ 6
  6. **Bucket coverage** — at least one `Stabilize` action exists (operations manager always needs an immediate next step)
- [ ] Each check returns a `Check` with `name`, `result` (PASS/FAIL), `notes`

### Sanity check
- [ ] Run on the Stage 2 output from Block 6. Confirm all checks pass.
- [ ] Manually corrupt the report (change a `standard_id` to `"STD-999"`). Confirm the corresponding check fails with a useful note.

**Done when:** Python checks correctly pass valid reports and fail corrupted ones.

---

## Block 8 — Stage 3 (LLM Verification) (~10 minutes)

**Goal:** Soft-signal verification that produces `VerificationResult` with optional confidence adjustments.

### Tasks
- [ ] Write `prompts/verification.txt`:
  - Role: independent verifier
  - Input: original triage output, full standards list, the report under review, the Python check results
  - Output: strict JSON matching `VerificationResult`
  - Instructions:
    - Confirm cited evidence actually justifies each hypothesis's confidence bucket
    - If evidence is thin for "High", suggest downgrade to Medium via `ConfidenceAdjustment`
    - Confirm each action logically addresses its linked hypothesis
    - Confirm the explanation is consistent with the hypotheses
    - Flag obvious omissions (e.g., Critical KPI breach with no addressing hypothesis)
    - Set `status: "FAIL"` only for critical issues (actions don't address hypotheses, explanation contradicts hypotheses); soft concerns become `confidence_adjustments` with `status: "PASS"`
- [ ] Write `pipeline/verification.py`:
  - Function `run_verification(triage: TriageOutput, report: ProductionIssueReport, standards: List[dict], python_checks: List[Check]) -> VerificationResult`
  - Calls `call_llm(MODEL_VERIFICATION, system, user, VerificationResult)`
  - Returns validated result

### Sanity check
- [ ] Run on Stage 2 output. Confirm:
  - `VerificationResult` validates
  - `checks` list is populated
  - At least one preset scenario produces a `confidence_adjustment`

**Done when:** Stage 3 LLM verifier returns coherent feedback on at least one scenario.

---

## Block 9 — Orchestrator + closed-loop retry (~10 minutes)

**Goal:** A single function that runs the full pipeline end-to-end with retry handling and graceful degradation.

### Tasks
- [ ] Write `pipeline/orchestrator.py` with function `run_pipeline(problem_statement, line_id, timestamp, notes="") -> dict` that returns:
  ```python
  {
      "triage": TriageOutput,
      "report": ProductionIssueReport,
      "python_checks": List[Check],
      "verification": VerificationResult,
      "unverified": bool,
      "retry_count": int,
      "failure_reasons": List[str],
  }
  ```
- [ ] Logic:
  1. Run Stage 1 (Triage)
  2. Run Stage 2 (Generation), no feedback first attempt
  3. Run Python checks
  4. If any Python check FAILs → record failures, retry Stage 2 once with feedback (the failed check notes), re-run Python checks
  5. Run Stage 3 (LLM Verification)
  6. If Stage 3 returns `status: "FAIL"` → record reason, retry Stage 2 once with combined feedback, re-run Python + Stage 3 checks
  7. After max one retry: apply confidence_adjustments to the report (lower buckets where verifier suggests), set `unverified=True` if anything still fails, return result
- [ ] Apply confidence adjustments by mutating the report (`hypotheses[rank-1].confidence = adjusted`)

### Sanity check
- [ ] Run the orchestrator on the throughput-drop preset. Confirm full result returns with `unverified=False` and `retry_count=0` (happy path).
- [ ] Force a hard failure by temporarily breaking a prompt. Confirm `retry_count=1` and `unverified=True` after second failure, with `failure_reasons` populated.

**Done when:** orchestrator runs end-to-end on the happy path AND degrades gracefully on a forced failure.

---

## Block 10 — Streamlit UI (~15 minutes)

**Goal:** Four-panel UI that exercises the full pipeline visibly.

### Tasks
- [ ] Write `app.py` with four panels:

**Panel 1 — Input**
- Factory dropdown (single option for V1, but a dropdown for visual completeness)
- Line dropdown (3 options)
- Timestamp picker (`st.datetime_input`, defaults to now)
- Problem statement text area
- Optional notes text area
- Four preset scenario buttons that pre-populate the inputs:
  - "Throughput drop on LINE-B2"
  - "Defect spike on LINE-A1"
  - "Supplier delay on LINE-C3"
  - "Safety incident on LINE-B2"
- "Run analysis" button

**Panel 2 — Live Execution Trace**
- Three collapsible expanders: "Stage 1 — Triage", "Stage 2 — Generation", "Stage 3 — Verification"
- Each shows the raw stage output as formatted JSON or a styled summary
- Timestamps for each stage
- If retry happened, show both attempts

**Panel 3 — Final Report**
- Problem summary at top
- Hypotheses section: each hypothesis as a card showing rank, cause, color-coded confidence bucket, evidence, standard reference
- Actions section: grouped by bucket (Stabilize / Investigate / Prevent), color-coded
- Explanation in a callout box

**Panel 4 — Verification Panel**
- Python checks: list with PASS/FAIL pills
- LLM verification status
- Confidence adjustments table (if any): hypothesis rank, original → adjusted, reason
- Big banner if `unverified=True` with all failure reasons

### Sanity check
- [ ] `streamlit run app.py`, click "Throughput drop on LINE-B2", confirm:
  - All three trace panels populate
  - Final report renders
  - Verification panel shows checks
- [ ] Repeat for the other 3 presets

**Done when:** all 4 presets render coherently in the UI from button click to final report.

---

## Block 11 — End-to-end test pass (~5 minutes)

**Goal:** Confirm the demo path is clean and the failure path is exercisable.

### Tasks
- [ ] Run all 4 presets back-to-back. Note any rough output and tighten the relevant prompt.
- [ ] Test the custom-input path: enter a free-text problem, confirm it works.
- [ ] Test a deliberately bad input ("everything is on fire") to confirm graceful behavior.
- [ ] Confirm at least one preset reliably produces a confidence adjustment for the demo.
- [ ] Confirm the `unverified` flag path works (can be triggered by temporarily breaking a prompt mid-demo if needed — don't actually break for the real demo).

**Done when:** all 4 presets demo cleanly, custom input works, graceful degradation is verified at least once.

---

## Block 12 — Pitch slide (~5 minutes)

**Goal:** One slide for the client walkthrough.

### Slide content
- **Title:** "Production Issue Resolution Assistant — Chorus AI Systems"
- **Visual:** Architecture diagram (Stage 1 → Stage 2 → Stage 3 with Python verification, retry loop visible)
- **Three bullets — "What makes this Chorus":**
  1. Three model families (Llama / DeepSeek / Qwen) — no single LLM is the source of truth
  2. Independent Python verification of every factual claim — zero hallucination tolerance
  3. Closed-loop retry with graceful degradation — system never silently fails
- **V2 roadmap (compressed):**
  - Real ERP integration
  - Embedding-based standards retrieval (BRAG-style)
  - Dual-verifier consensus
  - Drift detection and incident history

Tool: pick whatever's fastest — PowerPoint, Google Slides, or a single rendered PNG/PDF.

**Done when:** one slide exists and is ready to present.

---

## Time budget summary

| Block | Estimated time | Cumulative |
|---|---:|---:|
| Pre-flight | 2 | 2 |
| 1. Scaffolding | 5 | 7 |
| 2. Data + standards | 8 | 15 |
| 3. Schemas | 5 | 20 |
| 4. LLM client | 7 | 27 |
| 5. Stage 1 | 10 | 37 |
| 6. Stage 2 | 12 | 49 |
| 7. Python checks | 8 | 57 |
| 8. Stage 3 | 10 | 67 |
| 9. Orchestrator | 10 | 77 |
| 10. Streamlit UI | 15 | 92 |
| 11. E2E test | 5 | 97 |
| 12. Slide | 5 | 102 |

**Total: ~100 minutes.** Honest estimate. The 60-minute target was always optimistic for a real Chorus build. Plan for 90–105 minutes.

If time runs short, the cuts in priority order:
1. Skip preset scenario buttons in UI (use custom input only) — saves ~3 min
2. Skip Block 11 polish — saves ~5 min
3. Drop one preset scenario from testing — saves ~3 min
4. Skip the slide and do it post-build — saves ~5 min

What you do **not** cut: any of the three pipeline stages, Python verification, or the closed-loop retry. Those are the architectural argument.

---

## Risk register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Together AI free tier rate-limits during demo | Medium | Have one preset cached as JSON; if rate-limited, load from cache |
| One model returns malformed JSON repeatedly | Low | LLM client has built-in retry with error feedback |
| Verifier fails every time on every scenario | Low | Tune verifier prompt to be lenient on first build; tighten in V2 |
| Streamlit hot-reload breaks during demo | Low | Run with `--server.runOnSave false` for the demo session |
| Prompt edits cascade and break working scenarios | Medium | Test each preset after every prompt change |

---

## CLAUDE.md handoff content (for Block 1)

```markdown
# Production Assistant — Claude Code Context

## What this is
Chorus AI Systems MVP: three-stage pipeline (Triage → Generate → Verify) for apparel
manufacturing production issue triage. Single-session client demo.

## Architecture (locked)
- Stage 1 Triage: Llama 3.3 70B
- Stage 2 Generation: DeepSeek V3
- Stage 3 Verification: Qwen2.5 72B (LLM) + Python independent checks
- Fallback: Mistral/Mixtral 8x22B
- One retry on hard failure, then graceful `unverified` degradation

## Reference docs
- `Production_Assistant_Spec_v1.md` — stable architectural spec (don't edit during build)
- `Production_Assistant_Build_Plan_v1.md` — block-by-block build plan with done-when criteria

## Current block
[update this as you progress]

## Decisions log
See Spec section 11. Eight locked decisions. Don't relitigate during the build.

## What's out of scope
ERP integration, real RAG, time-series, multi-factory, formatted memo outputs, persistence, auth.
All deferred to V2.
```
