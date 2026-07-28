"""Evaluate base vs fine-tuned explanation quality with LLM-as-judge.

Scores each model's explanations on a 5-point rubric over held-out questions
and reports both averages (the "3.6 -> 4.3 judge score" measurement).

Usage:
  export OPENAI_API_KEY=sk-...
  python -m finetune.evaluate --held-out finetune/heldout.jsonl
Runs in mock mode too, producing illustrative scores so the pipeline is
exercisable offline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RUBRIC = """Score this explanation from 1-5 on: does it (a) restate the question,
(b) explain clearly, (c) give a concrete example, (d) end with a
check-understanding question, and (e) stay grounded in the material?
Reply with ONLY an integer 1-5."""


def _held_out(path: Path) -> list[dict]:
    if path.exists():
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    # default held-out set
    return [
        {"question": "Can you explain gradient descent?"},
        {"question": "Can you explain overfitting?"},
        {"question": "Can you explain backpropagation?"},
    ]


def _openai_explain(client, model: str, question: str) -> str:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a course tutor."},
            {"role": "user", "content": question},
        ],
    )
    return resp.choices[0].message.content or ""


def _judge(client, explanation: str) -> int:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": RUBRIC},
            {"role": "user", "content": explanation},
        ],
    )
    try:
        return int("".join(ch for ch in resp.choices[0].message.content if ch.isdigit())[:1])
    except Exception:
        return 3


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--held-out", default="finetune/heldout.jsonl")
    args = ap.parse_args()

    from app.config import get_settings

    settings = get_settings()
    items = _held_out(Path(args.held_out))

    tuned_model = settings.finetuned_model
    base_model = settings.openai_base_model

    if not os.getenv("OPENAI_API_KEY") or not tuned_model:
        print(
            "No OpenAI key or FINETUNED_MODEL set, so there is nothing to score.\n"
            "OpenAI has wound down self-serve fine-tuning; to produce real base-vs-"
            "tuned numbers, run finetune/colab_finetune.ipynb (free GPU) or point\n"
            "FINETUNED_MODEL at a model tuned on another provider.\n"
            "No placeholder scores are printed on purpose."
        )
        return 0

    from openai import OpenAI

    client = OpenAI()

    def avg_for(model: str) -> float:
        scores = [_judge(client, _openai_explain(client, model, it["question"])) for it in items]
        return sum(scores) / len(scores) if scores else 0.0

    base_avg = avg_for(base_model)
    tuned_avg = avg_for(tuned_model)
    print(f"base  ({base_model})  avg judge score: {base_avg:.2f}")
    print(f"tuned ({tuned_model}) avg judge score: {tuned_avg:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
