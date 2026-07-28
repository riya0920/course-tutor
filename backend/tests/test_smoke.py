"""End-to-end smoke tests. These run in mock mode (no API key needed), so they
double as the CI gate that the core loop stays wired together."""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Isolate storage per test run before importing the app.
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="tutor-test-"))
# Force offline mock mode so tests are deterministic regardless of any
# provider keys present in the ambient environment.
os.environ["LLM_PROVIDER"] = "mock"

from app.main import app  # noqa: E402

client = TestClient(app)

SAMPLE_MD = b"""# Photosynthesis
Photosynthesis is the process by which plants convert light energy into chemical
energy stored in glucose. Chlorophyll absorbs light in the chloroplast. The
Calvin Cycle fixes carbon dioxide into sugar using the products of the light
reactions.
"""


def _upload() -> str:
    resp = client.post(
        "/upload",
        files={"file": ("bio.md", SAMPLE_MD, "text/markdown")},
        data={"session_id": ""},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["chunks_indexed"] >= 1
    return body["session_id"]


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["mock_mode"] is True


def test_upload_and_chat_streams_citations():
    sid = _upload()
    with client.stream(
        "POST", "/chat", json={"session_id": sid, "message": "What is photosynthesis?"}
    ) as r:
        assert r.status_code == 200
        body = "".join(chunk for chunk in r.iter_text())
    assert '"type": "meta"' in body
    assert '"type": "done"' in body


def test_quiz_generate_and_grade_updates_progress():
    sid = _upload()
    quiz = client.post(
        "/quiz", json={"session_id": sid, "topic": "Photosynthesis", "n": 2}
    ).json()
    assert len(quiz["questions"]) == 2
    # answers must not leak to the client
    assert "answer_index" not in quiz["questions"][0]

    q0 = quiz["questions"][0]
    grade = client.post(
        "/quiz/grade",
        json={"session_id": sid, "question_id": q0["id"], "chosen_index": 0},
    ).json()
    assert grade["question_id"] == q0["id"]
    assert "correct" in grade

    prog = client.get(f"/progress/{sid}").json()
    assert prog["total_attempts"] == 1


def test_off_syllabus_is_redirected():
    sid = _upload()
    with client.stream(
        "POST",
        "/chat",
        json={"session_id": sid, "message": "Who won the 2018 World Cup?"},
    ) as r:
        body = "".join(chunk for chunk in r.iter_text())
    assert '"off_syllabus": true' in body
