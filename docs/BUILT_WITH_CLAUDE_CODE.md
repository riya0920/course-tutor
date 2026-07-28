# How this was built with Claude Code

This whole project — backend, frontend, evals, fine-tuning scaffolding, CI, and deploy
config — was built with Claude Code in an agentic loop. This is the daily-fluency evidence:
not "an AI helped," but a specific record of the workflow and where the agent loop needed a
human (or its own tests) to catch itself.

## Workflow shape

1. **Spec → decisions up front.** The build started from a written spec. Before writing code,
   the three decisions that actually change the build (scope, deploy approach, which keys exist)
   were pinned down, so the agent wasn't guessing architecture mid-stream.
2. **Backend-first, verify-as-you-go.** The core loop (upload → RAG chat → quiz → grade →
   mastery) was built and its smoke tests run *before* any frontend existed. Bugs surface
   cheaper at the API layer than through the UI.
3. **Mock mode as a design constraint, not an afterthought.** Requiring the whole app to run
   with zero keys forced clean seams: an `LLM` class with a mock backend, retrieval with a
   hashing fallback, a vector store with an in-memory fallback. That constraint is why the
   eval harness and CI can run without secrets.
4. **Browser verification.** The finished stack was driven in a real browser — ask a question,
   watch the SSE stream and citation render, run a quiz, watch the mastery bar update — rather
   than asserting it "should" work.

## What the agent loop got wrong, and how it was caught

- **`config.py` read the environment at class-definition time.** Settings like
  `GUARDRAILS_ENABLED` were bound once at import, so the eval harness's OFF-vs-ON toggle
  silently did nothing — both runs reported identical numbers. **The eval harness caught its
  own bug:** the OFF and ON columns were suspiciously equal. Fix: move all env reads into
  `Settings.__init__` so `get_settings.cache_clear()` genuinely re-reads. This is exactly the
  "evals as a checkable artifact" story — the measurement surfaced a defect the tests hadn't.
- **FastAPI startup didn't fire under `TestClient`.** The schema-creation `on_event("startup")`
  never ran because `TestClient` only fires lifespan events as a context manager, so the first
  tests failed with `no such table: sessions`. Fix: initialize the DB at import time *and*
  migrate to the modern `lifespan` handler.
- **A fragile similarity threshold for off-syllabus detection.** The first mock heuristic keyed
  off a cosine-similarity floor, which the hashing fallback made noisy (every pair has some
  non-zero similarity). Replaced with a lexical-overlap check — robust regardless of which
  embedding backend is live.
- **Port collision on the preview.** The dev environment already had another Vite app on 5173;
  the preview attached to *that* app. Fix: pin the frontend to a dedicated `strictPort` so it
  can't silently land on the wrong server.

## Custom slash commands / subagents

Not used for this build — it was a single coherent agent session where cross-file consistency
mattered more than parallel fan-out. The natural place to add a subagent later: expanding the
eval dataset from the 18-item seed to the full 100 (one agent per category, each verifying its
items against the corpus), since that's independent, verifiable, and volume work.
