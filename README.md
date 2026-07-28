# 🎓 Course Tutor

**▶ Live demo: [course-tutor.vercel.app](https://course-tutor.vercel.app)** — preloaded with a sample course, no upload needed. (Backend on Render's free tier sleeps after ~15 min idle, so the first request may take ~30–60s to wake.)

_Frontend: Vercel · Backend: Render (`course-tutor-api-z54m.onrender.com`) · LLM: Gemini 2.5 Flash._

An AI course tutor. Upload course material (PDF/Markdown), then **learn** (chat grounded in the material with citations), **get quizzed** (adaptive quizzes; wrong answers trigger targeted re-explanation + a follow-up), and **track progress** (per-concept mastery). Built with Claude Code.

> **Runs with zero setup.** With no API key set, the backend boots in an **offline mock mode** (deterministic tutor/quiz/grade responses + hashing-based retrieval), so you can clone and run the whole thing end-to-end before touching a key.

---

## 30-second demo

_Add a GIF here: upload → ask → cited answer → quiz → wrong answer → re-teach._

```
[ chat: "What is regularization?" ]
  → streamed, grounded answer
  → citation: [intro_to_ml.md]
  → ✓ grounded · TTFT 5ms · cache 87%

[ quiz: Gradient Descent ]
  → 4-choice question, graded server-side
  → wrong → misconception tag + re-explanation + follow-up
  → Mastery panel updates: Gradient Descent 1/2
```

---

## Architecture

```
Browser (React 18 + TypeScript + Tailwind, Vite)
  │  REST + SSE
  ▼
FastAPI (Python 3.11)
  ├── POST /upload    → PyMuPDF → chunk → embed → vector store
  ├── POST /chat (SSE)→ retrieve top-k → cached prompt → Claude (streaming)
  │                     ↳ input guardrail (off-syllabus) · grounding check · citations
  ├── POST /quiz      → structured-output quiz (Pydantic-validated)
  ├── POST /quiz/grade→ rubric grade → misconception tag → SQLite attempt
  ├── GET  /progress  → per-concept mastery
  └── POST /explain   → base/tuned explanation toggle (fine-tuning demo)
        ▼
  Vector store (ChromaDB, with NumPy fallback)   SQLite (sessions, attempts, mastery)
```

**Stack:** React/TS/Tailwind/Vite · FastAPI + SSE · Claude (Anthropic API) — documented primary · sentence-transformers (all-MiniLM-L6-v2) · ChromaDB · PyMuPDF · Pydantic v2 · custom eval harness · GitHub Actions.

**Pluggable LLM provider.** `LLM_PROVIDER=auto` (default) picks **Anthropic** if `ANTHROPIC_API_KEY` is set, else **Gemini** if `GEMINI_API_KEY` is set (via Gemini's OpenAI-compatible endpoint, thinking disabled for speed), else offline **mock**. Claude stays the documented primary because the prompt-caching cost measurement and "built with Claude Code" story depend on it; Gemini is a drop-in so the live demo can run on a Gemini key.

Every dependency in the retrieval path (sentence-transformers, ChromaDB, PyMuPDF) is **optional at runtime** — the app degrades gracefully to a hashing embedder + in-memory store + text parser so it always runs.

---

## The four things the spec cares about

### 1. Prompt caching (measured)
Each chat call is structured as a **cached prefix** (`[frozen system prompt + course-context digest]`, one `cache_control` breakpoint) plus an **uncached suffix** (the conversation). The response's `usage.cache_read_input_tokens` vs. `usage.input_tokens` is logged per request and surfaced in the UI footer (`cache 87%`). That split is the measurement behind the input-cost-reduction claim.

### 2. Structured output + guardrails
- **Output schema:** quizzes and grades come back via **forced tool use** and are validated against Pydantic models (`Quiz`, `Grade`). On validation failure: reject-and-retry once, then fail visibly — never ship malformed output to the UI.
- **Input guardrail:** an off-syllabus classifier redirects questions the material can't answer.
- **Grounding guardrail:** `lookup_source` must return a chunk above a similarity floor for an answer to count as supported; otherwise it's flagged ungrounded.

The three checks share one `GUARDRAILS_ENABLED` switch so the eval harness can produce **OFF vs ON** baselines from the same corpus.

### 3. Eval harness as a deploy gate
`evals/run_evals.py` runs a fixed QA dataset (answerable / off-syllabus / adversarial) and reports groundedness, off-syllabus handling, quiz validity, TTFT p50/p95, and the cached/uncached token split. GitHub Actions runs it on every PR and **blocks merge** if groundedness or off-syllabus handling regresses > 2 points vs. the committed baseline (`evals/main_metrics.json`). This is "write evals like unit tests," made checkable.

```bash
cd backend
python -m evals.run_evals --baseline    # guardrails OFF then ON, prints the delta
```

### 4. Fine-tuning component (AI Fund version)
`finetune/` generates instructor-style QA pairs (restate → explain → example → check-understanding), fine-tunes GPT-4o-mini via the OpenAI API, and evaluates base vs. tuned with an LLM-as-judge rubric. The app exposes it as a **base / tuned toggle** (`POST /explain`), so it's demoable, not just a claim.

```bash
cd backend
python -m finetune.generate_data --n 200 --out finetune/train.jsonl  # Claude drafts; you spot-check
export OPENAI_API_KEY=sk-...
python -m finetune.run_finetune --train finetune/train.jsonl --wait
python -m finetune.evaluate                                          # base vs tuned judge scores
```

---

## Run it locally

### Backend
```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # or .venv/bin/activate on macOS/Linux
pip install -r requirements.txt                          # or requirements-min.txt for mock mode only
cp .env.example .env                                     # optional: add ANTHROPIC_API_KEY for real answers
uvicorn app.main:app --reload --port 8000
```
No key in `.env`? It runs in mock mode. Check `GET /health` — `"mock_mode": true` confirms it.

### Frontend
```bash
cd frontend
npm install
npm run dev        # http://localhost:5180, proxies /chat, /quiz, ... to :8000
```

### Or one command (Docker)
```bash
ANTHROPIC_API_KEY=sk-... docker compose up   # backend on :8000; run the frontend separately
```

### Tests + evals
```bash
cd backend
pytest -q                          # end-to-end smoke tests (mock mode)
python -m evals.run_evals --baseline
```

---

## Deploy (live URL)

The repo is **one authenticated step from live** on each side:

- **Frontend → Vercel:** import the repo, set root to `frontend/`, add env `VITE_API_BASE=https://<backend-url>`. `vercel.json` is included.
- **Backend → Render:** "New → Blueprint" against this repo; `backend/render.yaml` provisions a Docker web service + a 1 GB disk. Set `ANTHROPIC_API_KEY` and `CORS_ORIGINS` (your Vercel URL) as secrets in the dashboard.

Both need your accounts/keys — see [docs/DEPLOY.md](docs/DEPLOY.md) for the click-by-click.

---

## Measurements that replace illustrative resume numbers

Run the harness with a real `ANTHROPIC_API_KEY` to fill these in — the moment a real number exists, the illustrative one dies.

| Claim | Real measurement source | Command |
|---|---|---|
| median TTFT | server + client timing, p50/p95 over eval requests | `python -m evals.run_evals` |
| unsupported answers OFF → ON | guardrails OFF vs ON eval runs | `python -m evals.run_evals --baseline` |
| input-cost reduction | cached vs uncached token logs | shown per-request in the UI footer |
| base → tuned judge score | base vs finetuned rubric eval | `python -m finetune.evaluate` |

_Current committed baseline (mock mode, for the CI gate):_ see `backend/evals/main_metrics.json`.

---

## How this was built (Claude Code)

See [docs/BUILT_WITH_CLAUDE_CODE.md](docs/BUILT_WITH_CLAUDE_CODE.md) — the agent workflow, what the loop got right, and what needed correction (e.g. the `config.py` env-read-timing bug the eval baseline surfaced).

---

## Honest limitations

Deliberate cuts that made this buildable in two weekends, and reads as judgment, not weakness:

- **Single-session, no auth.** State is keyed by an opaque server-side session id — no accounts, no multi-user classrooms.
- **One corpus at a time** per session.
- **In-memory chat history** — restarting the backend clears conversations (mastery/attempts persist in SQLite).
- **Mock mode ≠ quality mode.** The offline fallbacks (hashing embeddings, templated tutor/quiz text) exist so it always runs; real retrieval and answers need the keys.
- **Eval dataset is a seed** (18 items across the three categories). The spec's target is 100 (70/20/10) — the verification of each item is the actual work, so it's intentionally left to expand rather than auto-generated wholesale.
