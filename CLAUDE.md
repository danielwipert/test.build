# Production Assistant — Claude Code Context

## What this is
Chorus AI Systems MVP: three-stage pipeline (Triage → Generate → Verify) for apparel
manufacturing production issue triage. Single-session client demo.

## Architecture (locked)
- Stage 1 Triage: Llama 3.3 70B (OpenRouter)
- Stage 2 Generation: DeepSeek V3 (OpenRouter)
- Stage 3 Verification: Qwen2.5 72B (OpenRouter) + Python independent checks
- Fallback: Mixtral 8x22B (OpenRouter)
- One retry on hard failure, then graceful `unverified` degradation

## Deviation from spec
- Inference backend: **OpenRouter**, not Together AI (key in .env). All model strings updated.
- Built at repo root, not in `production-assistant/` subdir, since `.env` was already at root.

## Reference docs
- `planning/Production_Assistant_Spec_v1.md` — stable architectural spec
- `planning/Production_Assistant_Build_Plan_v1.md` — block-by-block build plan

## Run
```
pip install -r requirements.txt
streamlit run app.py
```
