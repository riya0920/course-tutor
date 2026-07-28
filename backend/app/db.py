"""SQLite persistence: sessions, quiz attempts, per-concept mastery.

State is keyed by an opaque server-side session id (no auth, no accounts —
see the spec's non-goals). The connection is created per-call to stay safe
across FastAPI's threadpool.
"""
from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from .config import get_settings
from .models import ConceptMastery, ProgressReport

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    corpus      TEXT,
    created_at  REAL
);

CREATE TABLE IF NOT EXISTS attempts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    question_id   TEXT NOT NULL,
    concept       TEXT NOT NULL,
    correct       INTEGER NOT NULL,
    misconception TEXT,
    created_at    REAL
);

CREATE INDEX IF NOT EXISTS idx_attempts_session ON attempts(session_id);

-- Pending quizzes so grading can look up the correct answer + concept without
-- trusting anything the client sends back.
CREATE TABLE IF NOT EXISTS quiz_questions (
    question_id  TEXT PRIMARY KEY,
    session_id   TEXT NOT NULL,
    concept      TEXT NOT NULL,
    answer_index INTEGER NOT NULL,
    rationale    TEXT,
    payload      TEXT
);
"""


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    settings = get_settings()
    conn = sqlite3.connect(settings.sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.executescript(_SCHEMA)


def ensure_session(session_id: str, corpus: str = "") -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (id, corpus, created_at) VALUES (?, ?, ?)",
            (session_id, corpus, time.time()),
        )


def set_session_corpus(session_id: str, corpus: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, corpus, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET corpus=excluded.corpus",
            (session_id, corpus, time.time()),
        )


def save_quiz_questions(session_id: str, questions: list) -> None:
    """Persist the answer key so `grade_answer` never trusts the client."""
    import json

    with _conn() as conn:
        for q in questions:
            conn.execute(
                "INSERT OR REPLACE INTO quiz_questions "
                "(question_id, session_id, concept, answer_index, rationale, payload) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    q.id,
                    session_id,
                    q.concept,
                    q.answer_index,
                    q.rationale,
                    json.dumps(q.model_dump()),
                ),
            )


def get_quiz_question(question_id: str) -> dict | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM quiz_questions WHERE question_id = ?", (question_id,)
        ).fetchone()
        return dict(row) if row else None


def record_attempt(
    session_id: str,
    question_id: str,
    concept: str,
    correct: bool,
    misconception: str | None,
) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO attempts "
            "(session_id, question_id, concept, correct, misconception, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, question_id, concept, int(correct), misconception, time.time()),
        )


def get_progress(session_id: str) -> ProgressReport:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT concept, COUNT(*) AS attempts, SUM(correct) AS correct "
            "FROM attempts WHERE session_id = ? GROUP BY concept ORDER BY concept",
            (session_id,),
        ).fetchall()

    concepts = [
        ConceptMastery(
            concept=r["concept"], attempts=r["attempts"], correct=r["correct"] or 0
        )
        for r in rows
    ]
    total_attempts = sum(c.attempts for c in concepts)
    total_correct = sum(c.correct for c in concepts)
    return ProgressReport(
        session_id=session_id,
        concepts=concepts,
        total_attempts=total_attempts,
        total_correct=total_correct,
    )
