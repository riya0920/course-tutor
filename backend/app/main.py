"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db, rag
from .config import get_settings
from .routers import chat, explain, progress, quiz, upload

# Initialise the schema at import time so the tables exist regardless of how the
# app is started (uvicorn, TestClient without a context manager, etc.).
db.init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    _maybe_seed_sample_corpus()
    yield


app = FastAPI(title="Course Tutor API", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(chat.router)
app.include_router(quiz.router)
app.include_router(progress.router)
app.include_router(explain.router)


@app.get("/health")
def health():
    from .llm import get_llm

    return {
        "status": "ok",
        "provider": settings.provider,
        "mock_mode": settings.mock_mode,
        "model": get_llm().model,
        "guardrails_enabled": settings.guardrails_enabled,
    }


SAMPLE_SESSION = "sample"


def _maybe_seed_sample_corpus() -> None:
    """Preload a bundled sample course under session id `sample` so a stranger
    can try the app with no upload (README checklist item)."""
    if rag.has_corpus(SAMPLE_SESSION):
        return
    corpus_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_corpus")
    if not os.path.isdir(corpus_dir):
        return
    for name in sorted(os.listdir(corpus_dir)):
        path = os.path.join(corpus_dir, name)
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                rag.index_document(SAMPLE_SESSION, name, fh.read())
    db.set_session_corpus(SAMPLE_SESSION, "sample course")
