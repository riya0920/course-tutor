"""POST /quiz — generate an adaptive quiz. POST /quiz/grade — grade one answer."""
from __future__ import annotations

import json

from fastapi import APIRouter
from pydantic import BaseModel

from .. import db, rag
from ..llm import get_llm
from ..models import Grade

router = APIRouter()


class QuizRequest(BaseModel):
    session_id: str
    topic: str = ""
    difficulty: str = "core"
    n: int = 4


@router.post("/quiz")
async def make_quiz(req: QuizRequest):
    db.ensure_session(req.session_id)
    # Retrieve broadly so the quiz spans the material, not just one query.
    chunks = rag.retrieve(req.session_id, req.topic or "key concepts overview", k=8)
    quiz = get_llm().generate_quiz(req.topic, req.difficulty, req.n, chunks)
    db.save_quiz_questions(req.session_id, quiz.questions)

    # Don't leak answers to the client; it grades server-side.
    public = quiz.model_dump()
    for q in public["questions"]:
        q.pop("answer_index", None)
        q.pop("rationale", None)
    return public


class GradeRequest(BaseModel):
    session_id: str
    question_id: str
    chosen_index: int


@router.post("/quiz/grade")
async def grade(req: GradeRequest) -> Grade:
    row = db.get_quiz_question(req.question_id)
    if not row:
        return Grade(
            question_id=req.question_id,
            correct=False,
            feedback="Question not found — it may have expired. Generate a new quiz.",
        )

    payload = json.loads(row["payload"])
    chunks = rag.retrieve(req.session_id, payload.get("prompt", ""), k=4)
    grade_result = get_llm().grade_answer(
        question_id=req.question_id,
        question_prompt=payload["prompt"],
        choices=payload["choices"],
        chosen_index=req.chosen_index,
        correct_index=row["answer_index"],
        rationale=row["rationale"] or "",
        concept=row["concept"],
        context_chunks=chunks,
    )

    db.record_attempt(
        session_id=req.session_id,
        question_id=req.question_id,
        concept=row["concept"],
        correct=grade_result.correct,
        misconception=grade_result.misconception_tag,
    )
    return grade_result
