"""Provider-agnostic LLM client (workstream 2).

LLM_PROVIDER=mock     -> no network, callers fall back to deterministic heuristics
LLM_PROVIDER=apertus  -> Swisscom Apertus 1.5 70B (Swiss-hosted, OpenAI-compatible)
LLM_PROVIDER=openai   -> OpenAI (hackathon credits)
"""
import json
import re

from app.config import settings


class LLMError(RuntimeError):
    pass


def is_mock() -> bool:
    return settings.llm_provider == "mock"


def model_version() -> str:
    """String recorded on every Match/Draft and in the audit log."""
    if settings.llm_provider == "apertus":
        return f"apertus:{settings.apertus_model}"
    if settings.llm_provider == "openai":
        return f"openai:{settings.openai_model}"
    return "mock:heuristic-v0"


_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        if settings.llm_provider == "apertus":
            _client = OpenAI(api_key=settings.apertus_api_key, base_url=settings.apertus_base_url)
        elif settings.llm_provider == "openai":
            _client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        else:
            raise LLMError(f"No client for provider {settings.llm_provider!r}")
    return _client


def complete_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Ask the model for a single JSON object and parse it. Raises LLMError on failure."""
    import time
    model = settings.apertus_model if settings.llm_provider == "apertus" else settings.openai_model
    kwargs = {}
    if settings.llm_provider == "openai":
        kwargs["response_format"] = {"type": "json_object"}
    print(f"  [LLM] Calling {settings.llm_provider} ({model}, max_tokens={max_tokens})...", flush=True)
    t0 = time.time()
    try:
        resp = _get_client().chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=settings.llm_temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
    except Exception as e:  # network, auth, rate limit
        elapsed = time.time() - t0
        print(f"  [LLM] Error after {elapsed:.2f}s: {e}", flush=True)
        raise LLMError(str(e)) from e
    elapsed = time.time() - t0
    content = resp.choices[0].message.content or ""
    print(f"  [LLM] Response received in {elapsed:.2f}s ({len(content)} chars)", flush=True)
    return parse_json(content)


def parse_json(text: str) -> dict:
    """Tolerant JSON extraction (Apertus has no JSON mode; it may wrap output in ``` fences)."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model did not return valid JSON: {e}: {text[:300]}") from e
