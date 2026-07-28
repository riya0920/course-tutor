# Deploy to a live URL

Two services: the React frontend on Vercel and the FastAPI backend on Render (Railway works too). Deploy the backend first so you have its URL for the frontend's env var.

## 1. Push to GitHub

```bash
cd course-tutor
git init && git add . && git commit -m "Initial commit"
gh repo create course-tutor --public --source=. --push   # or create it on github.com and push
```

## 2. Backend on Render (free tier)

1. In the Render dashboard, choose New, then Blueprint, and pick this repo. It reads `backend/render.yaml`.
2. Set these environment variables (the ones marked `sync: false` in the blueprint):
   - One LLM key, or neither for mock mode: `ANTHROPIC_API_KEY` for Claude, or `GEMINI_API_KEY` for Gemini. `LLM_PROVIDER=auto` picks whichever is present.
   - `CORS_ORIGINS`: your Vercel URL, e.g. `https://course-tutor.vercel.app` (add it after step 3).
3. Deploy, then confirm `https://<backend>.onrender.com/health` returns `{"status":"ok"}`.

The free tier sleeps after inactivity, so the first request after a nap is slow. It has no persistent disk, so uploads reset on a cold start; the sample course re-seeds on boot.

Railway alternative: New Project, deploy from the repo, set the root to `backend/`, and it detects the Dockerfile. Same env vars.

## 3. Frontend on Vercel

1. In Vercel, choose Add New, then Project, and import this repo.
2. Set the Root Directory to `frontend`.
3. Add the env var `VITE_API_BASE=https://<backend>.onrender.com`.
4. Deploy. Vercel uses the included `frontend/vercel.json` (framework: vite).
5. Copy the Vercel URL back into the backend's `CORS_ORIGINS` and redeploy the backend.

## 4. Verify

1. Open the Vercel URL. The sample course loads automatically, no upload needed.
2. Ask a question. You should see a streamed answer with a citation.
3. Start a quiz, answer it, and the mastery panel updates.

## Notes

- Keys never touch the repo. They live only in the Render and Vercel dashboards.
- To run entirely free with no LLM cost, deploy with no key and the live site runs in mock mode.
- SSE streaming works through Vercel and Render out of the box, no special config needed.
