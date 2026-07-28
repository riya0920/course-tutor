"""Kick off an OpenAI fine-tune of GPT-4o-mini on the generated QA pairs.

Usage:
  export OPENAI_API_KEY=sk-...
  python -m finetune.run_finetune --train finetune/train.jsonl

Prints the fine-tune job id; poll it, then set FINETUNED_MODEL to the resulting
model name so the app's base/tuned toggle can use it.

Cost: ~$5-15 for a few hundred pairs (see spec). Requires a real OPENAI_API_KEY;
this script does not run in mock mode by design (fine-tuning is a real job).
"""
from __future__ import annotations

import argparse
import os
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="finetune/train.jsonl")
    ap.add_argument("--base", default=os.getenv("OPENAI_BASE_MODEL", "gpt-4o-mini"))
    ap.add_argument("--wait", action="store_true", help="poll until the job finishes")
    args = ap.parse_args()

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY not set — fine-tuning needs a real key. Aborting.")
        return 1

    from openai import OpenAI

    client = OpenAI()

    print(f"uploading {args.train} ...")
    with open(args.train, "rb") as fh:
        file = client.files.create(file=fh, purpose="fine-tune")

    print(f"creating fine-tune job on {args.base} ...")
    try:
        job = client.fine_tuning.jobs.create(training_file=file.id, model=args.base)
    except Exception as e:
        msg = str(e)
        if "training_not_available" in msg or "winding down" in msg:
            print(
                "\nOpenAI has wound down self-serve fine-tuning, so this account "
                "can no longer create training jobs.\n"
                "The pipeline (data generation + judge eval) still works; point it "
                "at a provider that offers fine-tuning (Gemini/Vertex tuning, "
                "Together, Fireworks) by setting that provider's base URL and key."
            )
            return 2
        raise
    print(f"job id: {job.id}")

    if not args.wait:
        print("Poll with: client.fine_tuning.jobs.retrieve(job_id)")
        return 0

    while True:
        job = client.fine_tuning.jobs.retrieve(job.id)
        print(f"status: {job.status}")
        if job.status in ("succeeded", "failed", "cancelled"):
            break
        time.sleep(30)

    if job.status == "succeeded":
        print(f"\nFine-tuned model: {job.fine_tuned_model}")
        print(f"Set FINETUNED_MODEL={job.fine_tuned_model} to enable the tuned toggle.")
        return 0
    print(f"job ended: {job.status}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
