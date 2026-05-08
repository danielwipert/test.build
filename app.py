"""Streamlit UI — minimal four-panel layout for the Production Assistant MVP."""
from datetime import datetime

import streamlit as st

from pipeline.orchestrator import run_pipeline

st.set_page_config(page_title="Production Issue Resolution Assistant", layout="wide")
st.title("Production Issue Resolution Assistant")
st.caption("Chorus AI Systems — three-stage pipeline (Triage → Generate → Verify) with independent Python verification.")

PRESETS = {
    "— custom —": {"line": "LINE-B2", "problem": "", "notes": ""},
    "Throughput drop on LINE-B2": {
        "line": "LINE-B2",
        "problem": "Output dropped on Line B-2 starting around 8am. Operators report frequent stoppages.",
        "notes": "",
    },
    "Defect spike on LINE-A1": {
        "line": "LINE-A1",
        "problem": "QC flagged elevated stitch defects on Line A-1 in the last lot.",
        "notes": "",
    },
    "Supplier delay on LINE-C3": {
        "line": "LINE-C3",
        "problem": "Indigo dye batch from Supplier S-14 arrived hours late and held up Line C-3.",
        "notes": "",
    },
    "Safety incident on LINE-B2": {
        "line": "LINE-B2",
        "problem": "Near-miss reported at sewing station 4 on Line B-2 earlier this week.",
        "notes": "",
    },
}

# ---------- Panel 1: Input ----------
with st.container(border=True):
    st.subheader("1 · Input")
    preset_name = st.selectbox("Preset scenario", list(PRESETS.keys()))
    preset = PRESETS[preset_name]

    c1, c2 = st.columns(2)
    factory = c1.selectbox("Factory", ["FAC-01"], index=0)
    line_id = c2.selectbox("Line", ["LINE-A1", "LINE-B2", "LINE-C3"],
                            index=["LINE-A1", "LINE-B2", "LINE-C3"].index(preset["line"]))

    ts = st.text_input("Incident timestamp (ISO-8601)", value="2026-05-08T08:00:00")
    problem = st.text_area("Problem statement", value=preset["problem"], height=80)
    notes = st.text_area("Notes (optional)", value=preset["notes"], height=60)

    run_btn = st.button("Run analysis", type="primary", use_container_width=True)

if run_btn:
    if not problem.strip():
        st.error("Enter a problem statement.")
        st.stop()
    try:
        timestamp = datetime.fromisoformat(ts)
    except ValueError:
        st.error("Timestamp must be ISO-8601 (e.g., 2026-05-08T08:00:00).")
        st.stop()

    with st.spinner("Running three-stage pipeline…"):
        try:
            result = run_pipeline(problem, line_id, timestamp, notes)
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    triage = result["triage"]
    report = result["report"]
    py_checks = result["python_checks"]
    vr = result["verification"]

    # ---------- Panel 2: Live Execution Trace ----------
    with st.container(border=True):
        st.subheader("2 · Live Execution Trace")
        if result["retry_count"]:
            st.warning(f"Retry occurred ({result['retry_count']}x). All attempts shown below.")
        with st.expander("Stage 1 — Triage (Llama 3.3 70B)", expanded=False):
            st.json(triage.model_dump(mode="json"))
        with st.expander("Stage 2 — Generation (DeepSeek V3)", expanded=False):
            for i, att in enumerate(result["attempts"]):
                st.markdown(f"**Attempt {i+1}**")
                st.json(att["report"])
        with st.expander("Stage 3 — Verification (Qwen2.5 72B)", expanded=False):
            st.json(vr.model_dump(mode="json"))

    # ---------- Panel 3: Final Report ----------
    with st.container(border=True):
        st.subheader("3 · Final Report")
        if result["unverified"]:
            st.error("⚠ UNVERIFIED — verification did not pass after retry. Use with caution.")
            for r in result["failure_reasons"]:
                st.caption(r)

        st.markdown(f"**Problem summary** — {report.problem_summary}")
        st.markdown(f"**Incident time** — {report.incident_timestamp.isoformat()}")

        st.markdown("### Hypotheses")
        for h in sorted(report.hypotheses, key=lambda x: x.rank):
            color = {"High": "#d62728", "Medium": "#ff7f0e", "Low": "#999999"}[h.confidence]
            st.markdown(
                f"<div style='padding:8px;border-left:4px solid {color};margin-bottom:6px;background:#222;color:#fff;'>"
                f"<b>#{h.rank} · {h.cause}</b><br>"
                f"<span style='color:{color}'>Confidence: {h.confidence}</span> · Standard: <code>{h.standard_id}</code><br>"
                f"<i>Evidence:</i> {h.evidence}"
                f"</div>",
                unsafe_allow_html=True,
            )

        st.markdown("### Actions")
        bucket_colors = {"Stabilize": "#d62728", "Investigate": "#ff7f0e", "Prevent": "#2ca02c"}
        for bucket in ["Stabilize", "Investigate", "Prevent"]:
            items = [a for a in report.actions if a.bucket == bucket]
            if not items:
                continue
            st.markdown(
                f"<div style='color:{bucket_colors[bucket]};font-weight:bold;margin-top:8px'>{bucket}</div>",
                unsafe_allow_html=True,
            )
            for a in items:
                st.markdown(f"- **{a.action}** — {a.rationale}  _(→ hypothesis #{a.linked_hypothesis_rank})_")

        st.markdown("### Explanation")
        st.info(report.explanation)

    # ---------- Panel 4: Verification Panel ----------
    with st.container(border=True):
        st.subheader("4 · Verification")
        st.markdown("**Python checks (independent)**")
        for c in py_checks:
            icon = "✅" if c.result == "PASS" else "❌"
            st.markdown(f"{icon} **{c.name}** — {c.notes}")

        st.markdown("**LLM verifier checks**")
        for c in vr.checks:
            icon = "✅" if c.result == "PASS" else "❌"
            st.markdown(f"{icon} **{c.name}** — {c.notes}")

        if vr.confidence_adjustments:
            st.markdown("**Confidence adjustments applied**")
            for adj in vr.confidence_adjustments:
                st.markdown(f"- Hypothesis #{adj.hypothesis_rank}: **{adj.original} → {adj.adjusted}** — {adj.reason}")
        else:
            st.caption("No confidence adjustments.")

        if vr.overall_notes:
            st.caption(f"Verifier notes: {vr.overall_notes}")
