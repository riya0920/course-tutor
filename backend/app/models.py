"""Pydantic v2 schemas.

Every LLM output that reaches the UI is validated against one of these models
first. This is the "output schema" guardrail from the spec: reject-and-retry
once on validation failure, then fail visibly.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Difficulty = Literal["intro", "core", "stretch"]


# --------------------------------------------------------------------------- #
# Retrieval
# --------------------------------------------------------------------------- #
class Chunk(BaseModel):
    id: str
    text: str
    source: str = Field(description="Source document filename")
    page: Optional[int] = None
    score: float = Field(default=0.0, description="Cosine similarity to the query")


# --------------------------------------------------------------------------- #
# Quiz generation (structured tool output)
# --------------------------------------------------------------------------- #
class QuizQuestion(BaseModel):
    id: str
    concept: str = Field(description="The concept this question assesses")
    prompt: str
    choices: list[str] = Field(min_length=2, max_length=6)
    answer_index: int = Field(ge=0, description="Index into `choices` of the correct option")
    difficulty: Difficulty
    rationale: str = Field(description="Why the correct answer is correct")
    source_chunk_ids: list[str] = Field(
        default_factory=list, description="Chunks that support the question"
    )


class Quiz(BaseModel):
    topic: str
    questions: list[QuizQuestion] = Field(min_length=1)


# --------------------------------------------------------------------------- #
# Grading (structured tool output)
# --------------------------------------------------------------------------- #
class Grade(BaseModel):
    question_id: str
    correct: bool
    misconception_tag: Optional[str] = Field(
        default=None,
        description="Short tag naming the misconception, when the answer is wrong",
    )
    feedback: str = Field(description="Targeted re-explanation for the learner")
    followup_prompt: Optional[str] = Field(
        default=None, description="A follow-up question on the same concept"
    )


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
class Citation(BaseModel):
    chunk_id: str
    source: str
    page: Optional[int] = None
    quote: str


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatMeta(BaseModel):
    """Streamed as the final SSE event: citations + measurement telemetry."""
    citations: list[Citation] = Field(default_factory=list)
    grounded: bool = True
    off_syllabus: bool = False
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0
    output_tokens: int = 0
    ttft_ms: Optional[float] = None
    model: str = ""


# --------------------------------------------------------------------------- #
# Progress / mastery
# --------------------------------------------------------------------------- #
class ConceptMastery(BaseModel):
    concept: str
    attempts: int
    correct: int

    @property
    def rate(self) -> float:
        return self.correct / self.attempts if self.attempts else 0.0


class ProgressReport(BaseModel):
    session_id: str
    concepts: list[ConceptMastery]
    total_attempts: int
    total_correct: int
