"""Eval harness — treated as a first-class feature, not a test folder.

Runs the fixed QA dataset against the tutor pipeline and reports:
  - Groundedness: % answerable answers supported by a retrieved chunk
  - Unsupported rate: the inverse (the headline "17% -> 4%" number)
  - Off-syllabus handling: % of off/adversarial items correctly refused
  - Quiz validity: % generated quizzes passing schema + answerability
  - Latency: TTFT p50/p95
  - Cost: cached / uncached token split

Usage:
  python -m evals.run_evals                 # single run, guardrails per env
  python -m evals.run_evals --baseline      # run OFF then ON, print the delta
  python -m evals.run_evals --gate main_metrics.json   # CI gate vs a baseline

Runs in mock mode with no API key, so it works in CI. With a real key it
produces the real numbers that replace the illustrative ones in the README.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

# Make `app` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATASET = Path(__file__).parent / "dataset.jsonl"
CORPUS = Path(__file__).parent.parent / "sample_corpus"
EVAL_SESSION = "eval"


def _load_dataset() -> list[dict]:
    items = []
    with open(DATASET) as fh:
        for line in fh:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _seed_corpus() -> None:
    from app import rag

    for name in sorted(os.listdir(CORPUS)):
        path = CORPUS / name
        if path.is_file():
            rag.index_document(EVAL_SESSION, name, path.read_bytes())


def _run_once(label: str, guardrails_enabled: bool):
    # Configure BEFORE importing app modules that read settings.
    os.environ["GUARDRAILS_ENABLED"] = "true" if guardrails_enabled else "false"
    os.environ.setdefault("DATA_DIR", os.path.join(os.getcwd(), "eval_data"))

    # Fresh settings + a fresh in-memory corpus for a clean run.
    from app.config import get_settings

    get_settings.cache_clear()  # type: ignore[attr-defined]
    from app import guardrails as gr  # noqa: F401
    from app import rag
    from app.llm import ChatResult, get_llm
    from evals.metrics import RunMetrics, percentile

    # reset module-level singletons that captured old settings
    import app.llm as llm_mod

    llm_mod._llm = None

    _seed_corpus()
    llm = get_llm()
    items = _load_dataset()

    ttfts: list[float] = []
    cached = uncached = 0
    grounded_hits = 0
    n_answerable = 0
    refused_correct = 0
    n_refusal = 0

    for item in items:
        chunks = rag.retrieve(EVAL_SESSION, item["question"])
        check = gr.check_input(EVAL_SESSION, item["question"], chunks)

        if item["type"] in ("off_syllabus", "adversarial"):
            n_refusal += 1
            if check.off_syllabus:
                refused_correct += 1
            continue

        # answerable
        n_answerable += 1
        if check.off_syllabus:
            # wrongly refused an answerable question -> counts as unsupported
            continue

        t0 = time.time()
        result = ChatResult()
        parts = []
        ttft = None
        for tok in llm.stream_chat(item["question"], chunks, [], result):
            if ttft is None:
                ttft = (time.time() - t0) * 1000
            parts.append(tok)
        answer = "".join(parts)
        if ttft is not None:
            ttfts.append(ttft)
        cached += result.usage.cached_input_tokens
        uncached += result.usage.uncached_input_tokens

        if gr.is_grounded(EVAL_SESSION, answer or item["question"]):
            grounded_hits += 1

    groundedness = 100.0 * grounded_hits / n_answerable if n_answerable else 0.0
    off_handling = 100.0 * refused_correct / n_refusal if n_refusal else 0.0

    # Quiz validity: generate a few quizzes and confirm they validate + answers
    # point into choices.
    valid = total = 0
    for topic in ("Gradient Descent", "Regularization", "Neural Networks"):
        total += 1
        try:
            quiz = llm.generate_quiz(topic, "core", 3, rag.retrieve(EVAL_SESSION, topic, k=8))
            ok = all(0 <= q.answer_index < len(q.choices) for q in quiz.questions)
            if ok and quiz.questions:
                valid += 1
        except Exception:
            pass
    quiz_validity = 100.0 * valid / total if total else 0.0

    m = RunMetrics(
        label=label,
        groundedness=groundedness,
        unsupported_rate=100.0 - groundedness,
        off_syllabus_handling=off_handling,
        quiz_validity=quiz_validity,
        ttft_p50_ms=percentile(ttfts, 0.5),
        ttft_p95_ms=percentile(ttfts, 0.95),
        cached_tokens=cached,
        uncached_tokens=uncached,
        n_answerable=n_answerable,
        n_refusal_targets=n_refusal,
    )
    return m


def _print_table(rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    widths = {c: max(len(c), *(len(str(r[c])) for r in rows)) for c in cols}
    header = " | ".join(c.ljust(widths[c]) for c in cols)
    print(header)
    print("-" * len(header))
    for r in rows:
        print(" | ".join(str(r[c]).ljust(widths[c]) for c in cols))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", action="store_true", help="run guardrails OFF then ON")
    ap.add_argument("--gate", metavar="BASELINE_JSON", help="fail if metrics regress >2pts vs baseline")
    ap.add_argument("--out", metavar="PATH", help="write ON-run metrics to JSON")
    args = ap.parse_args()

    if args.baseline:
        off = _run_once("guardrails OFF", guardrails_enabled=False)
        on = _run_once("guardrails ON", guardrails_enabled=True)
        _print_table([off.to_row(), on.to_row()])
        print(
            f"\nHeadline: unsupported answers {off.unsupported_rate:.1f}% (OFF) "
            f"-> {on.unsupported_rate:.1f}% (ON)"
        )
        metrics = on
    else:
        enabled = os.getenv("GUARDRAILS_ENABLED", "true").lower() == "true"
        metrics = _run_once("run", guardrails_enabled=enabled)
        _print_table([metrics.to_row()])

    if args.out:
        Path(args.out).write_text(json.dumps(metrics.to_row(), indent=2))
        print(f"\nwrote {args.out}")

    if args.gate:
        baseline_path = Path(args.gate)
        if not baseline_path.exists():
            print(f"\n[gate] no baseline at {args.gate}; skipping (first run).")
            return 0
        baseline = json.loads(baseline_path.read_text())
        cur = metrics.to_row()
        regressions = []
        for key in ("groundedness_%", "off_syllabus_handling_%"):
            if cur[key] < baseline.get(key, 0) - 2.0:
                regressions.append(f"{key}: {baseline[key]} -> {cur[key]}")
        if regressions:
            print("\n[gate] FAIL — metrics regressed >2 points vs main:")
            for r in regressions:
                print(f"   - {r}")
            return 1
        print("\n[gate] PASS — no regression >2 points vs main.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
