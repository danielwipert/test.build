"""OpenRouter LLM client. OpenAI-compatible chat completions with JSON output + Pydantic validation."""
import json
import os
from typing import Type, TypeVar

import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

API_KEY = os.environ.get("OPENROUTER_API_KEY")
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter model strings
MODEL_TRIAGE = "meta-llama/llama-3.3-70b-instruct"
MODEL_GENERATION = "deepseek/deepseek-chat"
MODEL_VERIFICATION = "qwen/qwen-2.5-72b-instruct"
MODEL_FALLBACK = "mistralai/mixtral-8x22b-instruct"

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(Exception):
    pass


def _post(model: str, system: str, user: str, timeout: int = 90) -> str:
    if not API_KEY:
        raise LLMOutputError("OPENROUTER_API_KEY not set in environment")
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://chorus.ai/production-assistant",
        "X-Title": "Production Assistant MVP",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(ENDPOINT, headers=headers, json=payload, timeout=timeout)
    if r.status_code != 200:
        raise LLMOutputError(f"OpenRouter HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise LLMOutputError(f"Unexpected response shape: {e}; body: {str(data)[:500]}")


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        # remove ```json or ``` opener and closing ```
        lines = s.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    return s


def call_llm(model: str, system: str, user: str, schema: Type[T]) -> T:
    """Call a model, parse JSON, validate against schema. One retry on parse/validation failure."""
    schema_hint = (
        "\n\nReturn ONLY a single JSON object matching this schema. No prose, no markdown fences. "
        f"Schema (Pydantic): {schema.model_json_schema()}"
    )
    full_system = system + schema_hint
    last_err = None
    last_raw = None

    for attempt in range(2):
        if attempt == 0:
            user_msg = user
        else:
            user_msg = (
                f"{user}\n\n---\nYour previous response failed parsing/validation:\n"
                f"ERROR: {last_err}\nRAW: {last_raw[:500] if last_raw else ''}\n"
                f"Return a valid JSON object matching the schema. No fences."
            )
        raw = _post(model, full_system, user_msg)
        last_raw = raw
        cleaned = _strip_fences(raw)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            last_err = f"JSONDecodeError: {e}"
            continue
        try:
            return schema.model_validate(parsed)
        except ValidationError as e:
            last_err = f"ValidationError: {e}"
            continue

    raise LLMOutputError(f"call_llm failed after 2 attempts. Last error: {last_err}. Last raw: {last_raw[:500] if last_raw else ''}")
