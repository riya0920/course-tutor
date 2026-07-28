"""Generate ~N instructor-style QA pairs from the corpus for fine-tuning.

Claude drafts the pairs; you spot-check a sample (the verification is the work).
Output is OpenAI chat fine-tuning JSONL: each line is
  {"messages": [{"role": "system"...}, {"role":"user"...}, {"role":"assistant"...}]}

The assistant target follows a fixed explanation structure:
  restate -> explain -> example -> check-understanding question.

Usage:
  python -m finetune.generate_data --n 200 --out finetune/train.jsonl
Runs in mock mode (no key) producing templated pairs so the pipeline is
exercisable offline.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

SYSTEM = (
    "You are a course tutor. Explain the concept in four steps: restate the "
    "question, explain the idea, give a concrete example, then ask one "
    "check-understanding question."
)

CORPUS = Path(__file__).parent.parent / "sample_corpus"


def _concepts_and_text() -> list[tuple[str, str]]:
    from app import rag

    pairs = []
    for name in sorted(os.listdir(CORPUS)):
        p = CORPUS / name
        if not p.is_file():
            continue
        pages = rag.parse_document(name, p.read_bytes())
        for text, _ in pages:
            for para in text.split("\n\n"):
                para = para.strip()
                if len(para.split()) > 15:
                    title = para.split("\n")[0].lstrip("# ").strip()
                    pairs.append((title[:60], para))
    return pairs


def _mock_target(concept: str, body: str) -> str:
    first = " ".join(body.split()[:40])
    return (
        f"Let's break down {concept}. "
        f"In short: {first}. "
        f"For example, imagine applying {concept} to a simple case from the "
        f"material. "
        f"Check yourself: can you state {concept} in one sentence without "
        f"looking?"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--out", default="finetune/train.jsonl")
    args = ap.parse_args()

    from app.config import get_settings

    settings = get_settings()
    pairs = _concepts_and_text()
    if not pairs:
        print("no corpus paragraphs found")
        return 1

    client = None
    if not settings.mock_mode:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    rows = []
    i = 0
    while len(rows) < args.n:
        concept, body = pairs[i % len(pairs)]
        i += 1
        question = f"Can you explain {concept}?"
        if client is None:
            target = _mock_target(concept, body)
        else:
            resp = client.messages.create(
                model=settings.tutor_model,
                max_tokens=400,
                system=SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": f"Course material:\n{body}\n\nQuestion: {question}",
                    }
                ],
            )
            target = "".join(
                b.text for b in resp.content if getattr(b, "type", "") == "text"
            )
        rows.append(
            {
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": question},
                    {"role": "assistant", "content": target},
                ]
            }
        )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"wrote {len(rows)} QA pairs to {out}")
    print("Next: spot-check ~50 lines by hand, then run `python -m finetune.run_finetune`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
