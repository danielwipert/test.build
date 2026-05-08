# Production Issue Resolution Assistant — Spec v1

**Project:** Chorus AI Systems — Production Issue Resolution Assistant (MVP)
**Client domain:** Apparel manufacturing, multi-factory operations
**Build target:** ~60–90 minute live build, single-session demo
**Document type:** Stable architectural specification

---

## 1. Purpose

A manufacturing operations manager oversees several plants and production lines. When something goes wrong (output drop, defect spike, supplier delay, safety incident), the manager needs fast, evidence-grounded triage: what is happening, why it is likely happening, and what to do next.

The Production Issue Resolution Assistant accepts a short problem statement plus the affected factory/line context and returns a structured report containing ranked root-cause hypotheses, bucketed action items, and a brief explanation referencing the relevant process standards.

The system is a Chorus AI Systems showcase. It is **not** a single-LLM black box; it is a multi-stage, multi-model pipeline with verification layers, closed-loop retry, and Python-side independent verification of factual claims.

---

## 2. User & inputs

**Primary user:** Manufacturing operations manager.

**Inputs (per request):**
1. Short problem statement (free text, e.g., "output dropped on Line B-2 starting around 8am")
2. Factory ID + Line ID (selected from dropdowns)
3. Incident timestamp (when the issue began or was observed)
4. Optional: PWO ID, additional context notes

**Preset demo scenarios** (for the live walkthrough):
- Throughput drop
- Defect spike
- Supplier delay
- Safety incident

Each preset pre-populates the inputs for that scenario type.

---

## 3. Outputs

The system produces a `ProductionIssueReport` containing:

- **Problem summary** — one-sentence restatement of the issue
- **Ranked hypotheses** — 2 to 4 root-cause hypotheses, each with:
  - Rank (1 = most likely)
  - Cause statement
  - Confidence bucket: High / Medium / Low
  - Evidence (specific data points)
  - Process standard reference
- **Action items** — 3 to 6 concrete actions, each tagged:
  - `Stabilize` (immediate, next shift)
  - `Investigate` (gather more info, next 24h)
  - `Prevent` (systemic change, next sprint+)
  - Each action links to a hypothesis it addresses
- **Explanation** — 2 to 3 sentences synthesizing for the operations manager
- **Verification trace** — pass/fail status of each verification check, plus any confidence adjustments made

---

## 4. Architecture (Chorus three-stage pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: problem statement + factory/line + timestamp + data     │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — TRIAGE     (Llama 3.3 70B)                           │
│  Reads scenario data + problem statement                        │
│  Outputs: TriageOutput (problem_summary, affected_entities,     │
│  breached_kpis, category)                                       │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2 — GENERATION  (DeepSeek V3)                            │
│  Reads TriageOutput + standards.json + scenario data            │
│  Outputs: ProductionIssueReport (hypotheses, actions,           │
│  explanation)                                                   │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3 — VERIFICATION (Qwen2.5 72B)  +  Python checks         │
│                                                                 │
│  LLM checks:                                                    │
│   - Does evidence cited justify the confidence bucket?          │
│   - Do actions logically address the hypotheses?                │
│   - Is the explanation consistent with hypotheses?              │
│                                                                 │
│  Python checks (independent):                                   │
│   - Every cited metric value matches data.py                    │
│   - Every standard_id exists in standards.json                  │
│   - linked_hypothesis_rank points to a real hypothesis          │
│   - Pydantic schema validity                                    │
│                                                                 │
│  Outputs: VerificationResult (PASS/FAIL, checks,                │
│  confidence_adjustments)                                        │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
        ┌──────────────────────┴───────────────────────┐
        │                                              │
        ▼                                              ▼
   PASS or soft-FAIL with                  HARD FAIL (Python check
   confidence adjustments                   or LLM critical FAIL)
        │                                              │
        ▼                                              ▼
   Render final report                  Retry Stage 2 once with
                                        verifier feedback in prompt
                                                       │
                                                       ▼
                                        If second attempt fails:
                                        return result flagged
                                        `unverified` with reasons
```

**Closed-loop retry policy:** One retry on hard failure. After two failed attempts, return the latest result with an `unverified` flag and the verifier's notes visible in the UI. The system never hard-crashes — graceful degradation only.

**Observer diversity:** Three model families across the active pipeline (Meta, DeepSeek, Alibaba), with Mistral as a fourth-family fallback for any stage. This is a structural governance requirement, not a stylistic preference.

---

## 5. Models

| Stage | Model | Family | Why |
|---|---|---|---|
| Stage 1 — Triage | Llama 3.3 70B | Meta | Strong at structured extraction and classification |
| Stage 2 — Generation | DeepSeek V3 | DeepSeek | Strongest reasoner for open-ended hypothesis/action generation |
| Stage 3 — Verification | Qwen2.5 72B | Alibaba | Different family from generator; strong at constraint-checking |
| Fallback (any stage) | Mistral / Mixtral 8x22B | Mistral | Fourth-family fallback if a primary stage fails |

All inference via Together AI free tier.

---

## 6. Data model (Pydantic schemas)

### TriageOutput (Stage 1)
```python
class KPIBreach(BaseModel):
    metric: str                        # e.g., "throughput_pct"
    current_value: float
    baseline_value: float
    severity: Literal["Critical", "Warning", "Info"]

class TriageOutput(BaseModel):
    problem_summary: str
    incident_timestamp: datetime
    affected_entities: List[str]       # factory_id, line_id, pwo_id
    breached_kpis: List[KPIBreach]
    category: Literal["throughput", "defect", "supplier", "safety"]
```

### ProductionIssueReport (Stage 2 — primary output)
```python
class Hypothesis(BaseModel):
    rank: int                          # 1 = most likely
    cause: str
    confidence: Literal["High", "Medium", "Low"]
    evidence: str                      # cites real metrics
    standard_id: str                   # must exist in standards.json

class ActionItem(BaseModel):
    bucket: Literal["Stabilize", "Investigate", "Prevent"]
    action: str                        # imperative, concrete
    rationale: str
    linked_hypothesis_rank: int

class ProductionIssueReport(BaseModel):
    problem_summary: str
    incident_timestamp: datetime
    hypotheses: List[Hypothesis]       # 2-4 items
    actions: List[ActionItem]          # 3-6 items
    explanation: str                   # 2-3 sentences
```

### VerificationResult (Stage 3)
```python
class Check(BaseModel):
    name: str
    result: Literal["PASS", "FAIL"]
    notes: str

class ConfidenceAdjustment(BaseModel):
    hypothesis_rank: int
    original: Literal["High", "Medium", "Low"]
    adjusted: Literal["High", "Medium", "Low"]
    reason: str

class VerificationResult(BaseModel):
    status: Literal["PASS", "FAIL"]
    checks: List[Check]
    confidence_adjustments: List[ConfidenceAdjustment]
    overall_notes: str
```

---

## 7. Reference data

### Synthetic factory data (`data.py`)
- 1 factory: `FAC-01`
- 3 production lines: `LINE-A1`, `LINE-B2`, `LINE-C3`
- Per line: current throughput %, current error rate %, safety incidents this week, KPI baselines for each
- 3 incident log entries (mixed across lines, each with timestamp)
- 1 sample PWO per line with expected vs. actual start time (for supplier-delay scenario)

### Process standards (`standards.json`)
- 6 to 8 standards, each with `id`, `title`, `description`
- Cover: throughput baselines, defect-rate response, supplier-delay protocol, safety incident reporting, equipment downtime, quality thresholds
- Loaded once at app startup, full set passed into Stage 2 prompt

---

## 8. UI (Streamlit)

Four panels, top to bottom:

1. **Input panel** — factory/line dropdowns, timestamp picker, problem statement text box, four preset scenario buttons
2. **Live Execution Trace** — collapsible sections showing each stage's output as it streams (Triage → Generation → Verification). This is the portfolio argument made visible.
3. **Final Report** — the polished `ProductionIssueReport`, with hypotheses grouped by rank and actions grouped by bucket
4. **Verification Panel** — checks passed/failed, confidence adjustments made, any `unverified` flag with reasons

Color coding:
- KPI severity: Critical = red, Warning = amber, Info = blue
- Action bucket: Stabilize = red, Investigate = amber, Prevent = green
- Confidence: High = solid, Medium = lighter, Low = ghosted

---

## 9. Verification: what each layer actually does

### Python independent verification (hard rejects)
- Every `current_value` cited in any `evidence` string must match the value in `data.py`
- Every `standard_id` cited must exist in `standards.json`
- Every `linked_hypothesis_rank` must reference an actual hypothesis in the report
- Pydantic schema validity on all stage outputs

If any Python check fails → hard fail → retry Stage 2 once with feedback.

### Stage 3 LLM verification (soft signals)
- Does the cited evidence actually justify the claimed confidence bucket? (May produce a `ConfidenceAdjustment`)
- Do the actions logically address the hypotheses they link to?
- Is the explanation consistent with the hypotheses and evidence?
- Are there obvious omissions (e.g., a Critical KPI breach with no corresponding hypothesis)?

Soft failures produce `confidence_adjustments` rather than full regeneration. Critical LLM failures (e.g., "actions don't address any hypothesis") trigger a regeneration.

---

## 10. Out of scope (V1)

Explicitly deferred to V2+:
- ERP integration / live data ingestion
- Time-series metrics (V1 uses snapshots only)
- Real RAG with embeddings (V1 passes full standards set)
- Tag-based standard filtering
- Multiple factories beyond the single demo factory
- Maintenance request generation
- Formatted shift handoff note (memo format)
- Formatted supplier communication drafts
- Persistent storage / incident history
- Authentication / multi-user
- Drift detection across runs
- Dual-verifier consensus (Stage 3 currently single verifier)

These are pitched verbally on the slide as the V2 roadmap.

---

## 11. Decisions Log

| # | Decision | Resolution |
|---|---|---|
| 1 | Pipeline shape | Three-stage Chorus pipeline (Triage → Generate → Verify) with Python independent verification and closed-loop retry |
| 2 | Confidence representation | Rank + High/Medium/Low bucket hybrid |
| 3 | Process standards source | `standards.json` loaded at startup; full set passed to Stage 2 |
| 4 | Model assignments | Llama 3.3 70B (Triage), DeepSeek V3 (Generation), Qwen2.5 72B (Verification), Mistral fallback |
| 5 | Synthetic data scope | Minimal — 1 factory, 3 lines, hardcoded in `data.py` |
| 6 | Output schema | Locked per Section 6, with severity, linked_hypothesis_rank, category, confidence_adjustments, and incident_timestamp |
| 7 | Closed-loop retry policy | One retry on hard failure; second failure returns `unverified` flagged result with reasons |
| 8 | UI structure | Four-panel Streamlit (Input / Trace / Report / Verification) |

---

## 12. Done-when criteria for V1

The MVP is complete when:
- A user can select a preset scenario or enter a custom problem
- The pipeline runs all three stages and renders intermediate output in the trace panel
- Python verification catches at least one class of factual error (validated via a deliberately broken test prompt)
- Stage 3 LLM verification produces at least one confidence adjustment in at least one preset scenario
- A hard-failure retry path is exercised and renders the `unverified` flag correctly
- All four preset scenarios produce coherent reports end-to-end
- One pitch slide exists summarizing architecture and V2 roadmap

---

## 13. V2 roadmap (for the slide)

1. **Real ERP integration** — replace `data.py` with live API pulls
2. **Time-series KPI tracking** — trend detection, not just snapshots
3. **BRAG-style retrieval over standards corpus** — replace full-set pass-through with embedded retrieval
4. **Dual-verifier consensus** — Qwen + Mistral must agree before PASS
5. **Drift detection** — flag when current behavior diverges from historical norms
6. **Persistent incident history** — searchable past incidents, prior resolutions
7. **Action item exports** — formatted shift handoff notes, maintenance requests, supplier comms drafts
