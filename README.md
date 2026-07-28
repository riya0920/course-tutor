# Course Tutor

A study tool for your own course material. You upload a PDF or markdown file and then you can:

- ask questions about it and get answers that stay grounded in the source, with citations back to the chunks they came from,
- take quizzes it generates from the material, where a wrong answer gets you a short re-explanation and a follow-up question on the same idea,
- watch a simple per-concept mastery view fill in as you go.

Live demo: https://course-tutor.vercel.app

It's preloaded with a small sample ML course, so you can try it without uploading anything. The backend runs on Render's free tier and goes to sleep when nobody's using it, so the first request after an idle spell takes 30 to 60 seconds to wake up. After that it's quick.

The frontend is on Vercel, the backend on Render, and answers currently come from Gemini 2.0 Flash. The Gemini free tier is small (a couple hundred requests a day), so when it runs out the app falls back to canned answers with citations rather than erroring, and picks back up once the quota resets.

## Architecture

```
Browser (React + TypeScript + Tailwind, built with Vite)
    |
    |  REST and Server-Sent Events
    |
FastAPI backend (Python 3.11)
    /upload     parse the file, chunk it, embed, store
    /chat       retrieve chunks, run guardrails, stream the answer, cite sources
    /quiz       generate and grade questions (validated tool calls)
    /progress   per-concept mastery from the grading history
    /explain    same concept, base model vs fine-tuned model
    |
Vector store (ChromaDB, or an in-memory fallback)
SQLite (quiz attempts and mastery)
LLM (Gemini or Claude, or an offline mock)
```

## Running it locally

Backend:

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev        # localhost:5180, proxies API calls to :8000
```

You don't need an API key to run it. With no key set, the backend serves canned responses and uses a hashing-based retriever instead of real embeddings, so the whole thing works offline for development. `GET /health` tells you which mode you're in. To get real answers, put a key in `backend/.env` (copy `.env.example`); either `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` works.

## How it works

The frontend is React with TypeScript and Tailwind (Vite). The backend is FastAPI. Chat is streamed over SSE so answers show up token by token.

When you send a message, the backend retrieves the most relevant chunks of your document, builds a prompt around them, and streams back the model's answer. After the answer, it runs a grounding check that looks up whether the claims are actually supported by a chunk above a similarity threshold, then returns the citations plus some per-request stats (time to first token, token counts) that show up under each message.

Document handling is the usual pipeline. PyMuPDF pulls text out of PDFs, it gets chunked with overlap, embedded, and stored. Embeddings use `all-MiniLM-L6-v2` and the store is ChromaDB when they're installed; if they're not, it falls back to a lightweight hashing embedder and an in-memory store. That fallback is what lets it run with no setup, and it's also what the free deployment uses, since the full ML stack won't fit in 512MB of RAM.

Quiz generation and grading go through tool calls and every result is validated against a Pydantic schema before it reaches the UI. If validation fails it retries once and then errors loudly rather than shipping something malformed. Grading is checked server-side against the stored answer key so the client can't be trusted with it, and each attempt is written to SQLite, which is where the mastery view comes from.

### LLM provider

`LLM_PROVIDER` defaults to `auto`, which uses Anthropic if `ANTHROPIC_API_KEY` is set, otherwise Gemini if `GEMINI_API_KEY` is set, otherwise the offline mock. Gemini goes through its OpenAI-compatible endpoint, with thinking turned off since a yes/no classifier doesn't need it and it was eating the token budget. The live demo runs on Gemini because it's free. The prompt-caching work is Anthropic-specific, so if you set an Anthropic key you get the cached-prefix behaviour and the cache-hit numbers in the footer.

### Guardrails

There are three checks, all behind one `GUARDRAILS_ENABLED` flag:

1. An off-syllabus classifier that redirects questions the material can't answer instead of making something up.
2. Pydantic validation on all structured output (quizzes, grades).
3. The grounding check described above.

The single flag exists so the eval harness can run the same questions with guardrails off and on and compare.

### Evals

`backend/evals/run_evals.py` runs a fixed set of 100 questions (70 answerable from the corpus, 20 off-topic, 10 adversarial) and reports groundedness, how often off-topic questions get correctly refused, quiz validity, latency percentiles, and the cached/uncached token split.

```bash
cd backend
python -m evals.run_evals --baseline    # runs guardrails off, then on, and prints the difference
```

Running the same set with guardrails off and then on shows what the guardrails buy you. This is the deterministic baseline (the reproducible run that the CI gate checks against):

| metric | guardrails off | guardrails on |
| --- | --- | --- |
| off-topic questions refused | 0% | 93% |
| answers grounded in a source | 100% | 100% |
| quizzes passing schema and answerability | 100% | 100% |

GitHub Actions runs the suite on every PR and fails the build if groundedness or off-syllabus handling drops more than 2 points against the committed baseline in `evals/main_metrics.json`.

These are the offline baseline numbers, which are deterministic so CI can rely on them. Run the harness with a real provider key (and quota) to get real groundedness, latency, and token numbers. `EVAL_LIMIT=10` caps items per category for a quick real-provider run that stays under free-tier limits.

### Prompt caching

The chat call is structured so the cached part (system prompt plus a stable course digest) stays identical from turn to turn, and only the retrieved excerpts and the question change. On Claude that lets prompt caching reuse the prefix. Measured over a 10-turn session on Claude Sonnet (`python -m evals.caching_demo`):

- about 40% of input tokens are served from cache after the first turn,
- roughly 36% lower input cost for the session (cache reads are billed at a tenth of the normal input price).

The caching prefix has to clear the model's minimum cacheable length (1024 tokens on Sonnet, 2048 on Haiku), so with a small corpus this needs Sonnet or larger. Caching is Anthropic-specific; on Gemini or in mock mode the footer just shows 0%.

### Fine-tuning (optional)

`backend/finetune/` has scripts to generate instructor-style QA pairs from the corpus, fine-tune a small model on the explanation style, and score base vs. tuned with an LLM judge. The sidebar has an "Explain a concept" card with a base/tuned toggle so you can compare the two side by side. Data generation and the judge eval both run; the training step targeted OpenAI's GPT-4o-mini, but OpenAI has since wound down self-serve fine-tuning, so completing the run now needs a provider that still offers it (Gemini or Vertex tuning, Together, Fireworks, etc.). The scripts are written against the OpenAI SDK and would point at any OpenAI-compatible fine-tuning endpoint.

### Tracing

The LLM calls (chat classification, quiz generation, grading, source lookup) are wrapped for LangSmith tracing. It's off by default and does nothing unless you set `LANGSMITH_TRACING=true` and a `LANGSMITH_API_KEY`, so there's no dependency on it to run the app.

## Deploying

`docs/DEPLOY.md` has the steps. Short version: push to GitHub, deploy the backend on Render (the Dockerfile and `render.yaml` are set up for the free tier), then deploy `frontend/` on Vercel with `VITE_API_BASE` pointing at the backend and the backend's `CORS_ORIGINS` pointing back at the Vercel URL.

## Limitations

- No accounts or auth. State is keyed by a server-side session id.
- One document per session.
- Chat history lives in memory, so it resets if the backend restarts. Quiz attempts and mastery are in SQLite.
- The free deployment doesn't have a persistent disk, so uploads reset on a cold start. The sample course re-seeds itself on boot.
- The eval set is small right now (18 questions). It's meant to grow to about 100; the work there is checking each item by hand, not generating more.
