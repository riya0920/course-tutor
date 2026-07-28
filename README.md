# Course Tutor

A study tool for your own course material. You upload a PDF or markdown file and then you can:

- ask questions about it and get answers that stay grounded in the source, with citations back to the chunks they came from,
- take quizzes it generates from the material, where a wrong answer gets you a short re-explanation and a follow-up question on the same idea,
- watch a simple per-concept mastery view fill in as you go.

Live demo: https://course-tutor.vercel.app

It's preloaded with a small sample ML course, so you can try it without uploading anything. The backend runs on Render's free tier and goes to sleep when nobody's using it, so the first request after an idle spell takes 30-60s to wake up. After that it's quick.

The frontend is on Vercel, the backend on Render, and answers currently come from Gemini 2.5 Flash.

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

You don't need an API key to run it. With no key set, the backend serves canned responses and uses a hashing-based retriever instead of real embeddings, so the whole thing works offline for development. `GET /health` tells you which mode you're in. To get real answers, put a key in `backend/.env` (copy `.env.example`) — either `ANTHROPIC_API_KEY` or `GEMINI_API_KEY` works.

## How it works

The frontend is React + TypeScript + Tailwind (Vite). The backend is FastAPI. Chat is streamed over SSE so answers show up token by token.

When you send a message, the backend retrieves the most relevant chunks of your document, builds a prompt around them, and streams back the model's answer. After the answer, it runs a grounding check — it looks up whether the claims are actually supported by a chunk above a similarity threshold — and returns the citations plus some per-request stats (time to first token, token counts) that show up under each message.

Document handling is the usual pipeline: PyMuPDF pulls text out of PDFs, it gets chunked with overlap, embedded, and stored. Embeddings use `all-MiniLM-L6-v2` and the store is ChromaDB when they're installed; if they're not, it falls back to a lightweight hashing embedder and an in-memory store. That fallback is what lets it run with no setup, and it's also what the free deployment uses (the full ML stack won't fit in 512MB of RAM).

Quiz generation and grading go through tool calls and every result is validated against a Pydantic schema before it reaches the UI. If validation fails it retries once and then errors loudly rather than shipping something malformed. Grading is checked server-side against the stored answer key so the client can't be trusted with it, and each attempt is written to SQLite, which is where the mastery view comes from.

### LLM provider

`LLM_PROVIDER` defaults to `auto`, which uses Anthropic if `ANTHROPIC_API_KEY` is set, otherwise Gemini if `GEMINI_API_KEY` is set, otherwise the offline mock. Gemini goes through its OpenAI-compatible endpoint (with thinking turned off, since a yes/no classifier doesn't need it and it was eating the token budget). The live demo runs on Gemini because it's free; the prompt-caching work is Anthropic-specific, so if you set an Anthropic key you get the cached-prefix behaviour and the cache-hit numbers in the footer.

### Guardrails

There are three checks, all behind one `GUARDRAILS_ENABLED` flag:

1. An off-syllabus classifier that redirects questions the material can't answer instead of making something up.
2. Pydantic validation on all structured output (quizzes, grades).
3. The grounding check described above.

The single flag exists so the eval harness can run the same questions with guardrails off and on and compare.

### Evals

`backend/evals/run_evals.py` runs a fixed set of questions (some answerable from the corpus, some off-topic, some adversarial) and reports groundedness, how often off-topic questions get correctly refused, quiz validity, latency percentiles, and the cached/uncached token split.

```bash
cd backend
python -m evals.run_evals --baseline    # runs guardrails off, then on, and prints the difference
```

GitHub Actions runs the suite on every PR and fails the build if groundedness or off-syllabus handling drops more than 2 points against the committed baseline in `evals/main_metrics.json`.

The numbers you get in mock mode are placeholders. Run it with a real key to get numbers worth quoting.

### Fine-tuning (optional)

`backend/finetune/` has scripts to generate instructor-style QA pairs from the corpus, fine-tune GPT-4o-mini on the explanation style, and score base vs. tuned with an LLM judge. The app has a base/tuned toggle (`POST /explain`) so you can actually compare them rather than just claim it. This part needs an OpenAI key and costs a few dollars to run.

## Deploying

`docs/DEPLOY.md` has the steps. Short version: push to GitHub, deploy the backend on Render (the Dockerfile and `render.yaml` are set up for the free tier), then deploy `frontend/` on Vercel with `VITE_API_BASE` pointing at the backend and the backend's `CORS_ORIGINS` pointing back at the Vercel URL.

## Limitations

- No accounts or auth. State is keyed by a server-side session id.
- One document per session.
- Chat history lives in memory, so it resets if the backend restarts. Quiz attempts and mastery are in SQLite.
- The free deployment doesn't have a persistent disk, so uploads reset on a cold start. The sample course re-seeds itself on boot.
- The eval set is small right now (18 questions). It's meant to grow to ~100; the work there is checking each item by hand, not generating more.

## Notes

This was built with Claude Code; `docs/BUILT_WITH_CLAUDE_CODE.md` has some notes on how it went, including a couple of bugs worth remembering (the config values were being read at import time, which quietly broke the guardrails-on/off comparison until the eval output looked suspicious).
