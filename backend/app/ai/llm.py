"""Provider-agnostic LLM client (workstream 2).

LLM_PROVIDER=mock     -> no network, callers fall back to deterministic heuristics
LLM_PROVIDER=apertus  -> Swisscom Apertus 1.5 70B (Swiss-hosted, OpenAI-compatible)
LLM_PROVIDER=openai   -> OpenAI (hackathon credits)
"""
import hashlib
import json
import re
import threading
import time

from app.config import DATA_DIR, settings

CACHE_DIR = DATA_DIR / "llm_cache"


class LLMError(RuntimeError):
    pass


_rate_lock = threading.Lock()
_next_slot = 0.0


def _wait_for_rate_limit() -> None:
    """Space out request starts to at most LLM_MAX_RPS per second, across all threads."""
    global _next_slot
    with _rate_lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + 1.0 / settings.llm_max_rps
    time.sleep(max(0.0, slot - now))


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
            _client = OpenAI(api_key=settings.apertus_api_key, base_url=settings.apertus_base_url, max_retries=4)
        elif settings.llm_provider == "openai":
            _client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url, max_retries=4)
        else:
            raise LLMError(f"No client for provider {settings.llm_provider!r}")
    return _client


def complete_json(system: str, user: str, max_tokens: int = 1500) -> dict:
    """Ask the model for a single JSON object and parse it. Raises LLMError on failure."""
    model = settings.apertus_model if settings.llm_provider == "apertus" else settings.openai_model
    key = hashlib.sha256(json.dumps([settings.llm_provider, model, settings.llm_temperature, system, user, max_tokens],
                                    ensure_ascii=False).encode()).hexdigest()
    cache_file = CACHE_DIR / f"{key}.json"
    if settings.llm_cache and cache_file.exists():
        print(f"  [LLM] cache hit ({settings.llm_provider})", flush=True)
        return json.loads(cache_file.read_text())

    kwargs = {}
    if settings.llm_provider == "openai":
        kwargs["response_format"] = {"type": "json_object"}
    for attempt in (1, 2):  # retry once: long answers are sometimes cut off or malformed
        _wait_for_rate_limit()
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
            print(f"  [LLM] Error after {time.time() - t0:.2f}s: {e}", flush=True)
            raise LLMError(str(e)) from e
        content = resp.choices[0].message.content or ""
        print(f"  [LLM] Response received in {time.time() - t0:.2f}s ({len(content)} chars)", flush=True)
        try:
            out = parse_json(content)
            break
        except LLMError as e:
            if attempt == 2:
                raise
            print(f"  [LLM] Invalid JSON, retrying once: {str(e)[:120]}", flush=True)
    if settings.llm_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file.write_text(json.dumps(out, ensure_ascii=False))
    return out


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
