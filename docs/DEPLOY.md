# Deploy to a live URL

Two services: the React frontend (Vercel) and the FastAPI backend (Render or Railway).
Deploy the backend first so you have its URL for the frontend's env var.

## 1. Push to GitHub
```bash
cd course-tutor
git init && git add . && git commit -m "Initial commit"
gh repo create course-tutor --public --source=. --push   # or create on github.com and push
```

## 2. Backend → Render (free tier)
1. Render dashboard → **New → Blueprint** → pick this repo. It reads `backend/render.yaml`.
2. Set these environment variables (marked `sync: false` in the blueprint) in the dashboard:
   - **One LLM key** (or neither for mock mode): `ANTHROPIC_API_KEY` for Claude, **or** `GEMINI_API_KEY` for Gemini. `LLM_PROVIDER=auto` picks whichever is present.
   - `CORS_ORIGINS` — your Vercel URL, e.g. `https://course-tutor.vercel.app` (add it after step 3).
3. Deploy. Confirm `https://<backend>.onrender.com/health` returns `{"status":"ok"}`.

> Free-tier Render sleeps after inactivity; the first request after a nap is slow. The 1 GB disk persists ChromaDB + SQLite between deploys.

**Railway alternative:** New Project → Deploy from repo → set root to `backend/`, it detects the Dockerfile. Same env vars.

## 3. Frontend → Vercel
1. Vercel → **Add New → Project** → import this repo.
2. Set **Root Directory** to `frontend`.
3. Add env var `VITE_API_BASE=https://<backend>.onrender.com`.
4. Deploy. Vercel uses the included `frontend/vercel.json` (framework: vite).
5. Copy the Vercel URL back into the backend's `CORS_ORIGINS` and redeploy the backend.

## 4. Verify
- Open the Vercel URL. The sample course loads automatically (no upload needed).
- Ask a question → you should see a streamed, cited answer.
- Start a quiz → answer → the Mastery panel updates.

## Notes
- **Keys never touch the repo.** They live only in the Render/Vercel dashboards.
- To run entirely free with no LLM cost, deploy with no `ANTHROPIC_API_KEY` — the live site runs in mock mode.
- SSE streaming works through Vercel + Render out of the box; no special config needed.
