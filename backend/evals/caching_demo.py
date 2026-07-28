"""Measure Anthropic prompt-caching savings over a multi-turn session.

Runs ~10 questions against the sample corpus, all in one session so the cached
course-digest prefix (system prompt + course reference) is reused turn to turn.
Reports the cached vs uncached input-token split and the resulting input-cost
reduction. This is the real measurement behind the "input-cost reduction" claim.

Needs ANTHROPIC_API_KEY. Cost is a few cents; use a cheap model to keep it low:
    TUTOR_MODEL=claude-haiku-4-5-20251001 python -m evals.caching_demo

Prompt caching is Anthropic-specific, so this only runs on the Claude provider.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CORPUS = Path(__file__).parent.parent / "sample_corpus"
SESSION = "cache-demo"

QUESTIONS = [
    "What is supervised learning?",
    "How does overfitting happen?",
    "What is the difference between L1 and L2 regularization?",
    "What does the learning rate control?",
    "What is backpropagation?",
    "Explain the bias variance tradeoff.",
    "How does a random forest work?",
    "What is a support vector machine?",
    "What does principal component analysis do?",
    "What is dropout and why does it help?",
]

# Anthropic pricing multipliers relative to base input price.
CACHE_READ_MULT = 0.1   # cached tokens are read at ~10% of the input price


def main() -> int:
    os.environ["LLM_PROVIDER"] = "anthropic"

    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    settings = get_settings()
    if settings.provider != "anthropic":
        print("Set ANTHROPIC_API_KEY to run the caching demo.")
        return 1

    from app import rag
    from app.llm import ChatResult, get_llm
    import app.llm as llm_mod

    llm_mod._llm = None

    for name in sorted(os.listdir(CORPUS)):
        p = CORPUS / name
        if p.is_file():
            rag.index_document(SESSION, name, p.read_bytes())

    llm = get_llm()
    print(f"model: {llm.model}\n")

    history: list[dict] = []
    total_cached = total_uncached = total_output = 0

    print(f"{'turn':>4}  {'cached_in':>10}  {'uncached_in':>12}  {'out':>6}")
    for i, q in enumerate(QUESTIONS, 1):
        chunks = rag.retrieve(SESSION, q)
        result = ChatResult()
        answer = "".join(llm.stream_chat(q, chunks, history, result, session_id=SESSION))
        history.append({"role": "user", "content": q})
        history.append({"role": "assistant", "content": answer})
        u = result.usage
        total_cached += u.cached_input_tokens
        total_uncached += u.uncached_input_tokens
        total_output += u.output_tokens
        print(f"{i:>4}  {u.cached_input_tokens:>10}  {u.uncached_input_tokens:>12}  {u.output_tokens:>6}")

    total_in = total_cached + total_uncached
    hit_rate = 100.0 * total_cached / total_in if total_in else 0.0

    # Input cost with caching vs. sending everything uncached each turn.
    with_cache = total_uncached + total_cached * CACHE_READ_MULT
    without_cache = total_in
    reduction = 100.0 * (1 - with_cache / without_cache) if without_cache else 0.0

    print("\n--- caching summary over", len(QUESTIONS), "turns ---")
    print(f"cached input tokens:   {total_cached}")
    print(f"uncached input tokens: {total_uncached}")
    print(f"cache hit rate:        {hit_rate:.1f}%")
    print(f"input-cost reduction:  {reduction:.1f}%  (cache reads at {CACHE_READ_MULT}x price)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
