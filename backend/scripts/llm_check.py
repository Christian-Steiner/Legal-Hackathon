"""Check that the configured LLM provider works (key, URL, model, JSON output).

    uv run python -m scripts.llm_check        (or: make llm-check)
"""
import sys
import time

from app.ai import llm
from app.config import settings


def main() -> None:
    print(f"Provider: {settings.llm_provider}  model: {llm.model_version()}")
    if llm.is_mock():
        print("LLM_PROVIDER=mock - set LLM_PROVIDER=apertus (or openai) and the key in backend/.env")
        sys.exit(1)
    t = time.time()
    try:
        out = llm.complete_json(
            "Answer with ONE JSON object only.",
            'Return {"ok": true, "language": "<the language of this word: Datenschutz>"}',
            max_tokens=50,
        )
    except llm.LLMError as e:
        print(f"FAILED after {time.time() - t:.1f}s: {e}")
        sys.exit(1)
    print(f"OK in {time.time() - t:.1f}s -> {out}")


if __name__ == "__main__":
    main()
