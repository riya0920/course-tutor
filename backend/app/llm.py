"""LLM access layer for Claude (Anthropic API), with a full offline mock.

What lives here:
- Streaming tutor chat with **prompt caching** (a cached system+context prefix,
  an uncached conversation suffix) and per-request cached/uncached token logging.
- **Structured output** for quizzes and grading via forced tool use, validated
  against Pydantic schemas with a single reject-and-retry.
- A cheap **off-syllabus classifier** used by the guardrails layer.
- A deterministic **mock backend** so everything runs with no API key.
"""
from __future__ import annotations

import json
import re
import textwrap
import uuid
from dataclasses import dataclass, field
from typing import Iterator, Optional

from .config import get_settings
from .models import Chunk, Grade, Quiz
from .tracing import traced
from .prompts import (
    GRADE_SYSTEM,
    OFF_SYLLABUS_CLASSIFIER,
    QUIZ_SYSTEM,
    TUTOR_SYSTEM,
)

# --------------------------------------------------------------------------- #
# Tool schemas (structured output)
# --------------------------------------------------------------------------- #
QUIZ_TOOL = {
    "name": "generate_quiz",
    "description": "Return an adaptive quiz grounded in the course material.",
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "concept": {"type": "string"},
                        "prompt": {"type": "string"},
                        "choices": {"type": "array", "items": {"type": "string"}},
                        "answer_index": {"type": "integer"},
                        "difficulty": {"type": "string", "enum": ["intro", "core", "stretch"]},
                        "rationale": {"type": "string"},
                        "source_chunk_ids": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "id", "concept", "prompt", "choices",
                        "answer_index", "difficulty", "rationale",
                    ],
                },
            },
        },
        "required": ["topic", "questions"],
    },
}

GRADE_TOOL = {
    "name": "grade_answer",
    "description": "Grade a learner's answer and give targeted feedback.",
    "input_schema": {
        "type": "object",
        "properties": {
            "question_id": {"type": "string"},
            "correct": {"type": "boolean"},
            "misconception_tag": {"type": ["string", "null"]},
            "feedback": {"type": "string"},
            "followup_prompt": {"type": ["string", "null"]},
        },
        "required": ["question_id", "correct", "feedback"],
    },
}


_STOPWORDS = {
    "what", "which", "when", "where", "does", "your", "about", "from", "that",
    "this", "with", "have", "into", "explain", "describe", "tell", "would",
    "could", "should", "there", "their", "them", "then", "than", "were",
}


@dataclass
class Usage:
    cached_input_tokens: int = 0
    uncached_input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class ChatResult:
    """Populated as a side-channel while streaming."""
    usage: Usage = field(default_factory=Usage)


def _format_context(chunks: list[Chunk]) -> str:
    parts = []
    for c in chunks:
        loc = f" (p.{c.page})" if c.page else ""
        parts.append(f"[chunk {c.id[:8]} — {c.source}{loc}]\n{c.text}")
    return "\n\n".join(parts)


class LLM:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.provider = self.settings.provider
        self._client = None
        self._gemini = None
        if self.provider == "anthropic":
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.settings.anthropic_api_key)
        elif self.provider == "gemini":
            # Gemini via its OpenAI-compatible endpoint (uses the openai SDK).
            from openai import OpenAI

            self._gemini = OpenAI(
                api_key=self.settings.gemini_api_key,
                base_url=self.settings.gemini_base_url,
            )

    @property
    def model(self) -> str:
        if self.provider == "anthropic":
            return self.settings.tutor_model
        if self.provider == "gemini":
            return self.settings.gemini_model
        return "mock"

    # ------------------------------------------------------------------ #
    # Chat (streaming)
    # ------------------------------------------------------------------ #
    def stream_chat(
        self,
        message: str,
        context_chunks: list[Chunk],
        history: list[dict],
        result: ChatResult,
        session_id: str = "",
    ) -> Iterator[str]:
        if self.provider == "mock":
            yield from self._mock_chat(message, context_chunks, result)
            return
        if self.provider == "gemini":
            # Fall back to the offline path if the provider errors (e.g. the
            # free-tier daily quota is exhausted), so the demo never breaks.
            try:
                yield from self._gemini_chat(message, context_chunks, history, result)
            except Exception:
                if self.settings.llm_strict:
                    raise
                yield from self._mock_chat(message, context_chunks, result)
            return

        # Cached prefix = frozen system prompt + a STABLE course digest (same
        # every turn, so Anthropic prompt caching reuses it). The per-turn
        # retrieved chunks are volatile, so they go in the (uncached) user
        # message alongside the question, after the cache breakpoint.
        from . import rag

        digest = rag.course_digest(session_id) if session_id else _format_context(context_chunks)
        retrieved = _format_context(context_chunks)
        system = [
            {"type": "text", "text": TUTOR_SYSTEM},
            {
                "type": "text",
                "text": "Course reference material:\n" + digest,
                "cache_control": {"type": "ephemeral"},
            },
        ]
        user_turn = (
            f"Relevant excerpts for this question:\n{retrieved}\n\nQuestion: {message}"
            if retrieved
            else message
        )
        messages = history + [{"role": "user", "content": user_turn}]

        with self._client.messages.stream(
            model=self.settings.tutor_model,
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text
            final = stream.get_final_message()

        u = final.usage
        result.usage = Usage(
            cached_input_tokens=getattr(u, "cache_read_input_tokens", 0) or 0,
            uncached_input_tokens=(u.input_tokens or 0)
            + (getattr(u, "cache_creation_input_tokens", 0) or 0),
            output_tokens=u.output_tokens or 0,
        )

    def _mock_chat(
        self, message: str, chunks: list[Chunk], result: ChatResult
    ) -> Iterator[str]:
        if not chunks:
            text = (
                "I can't find anything in the uploaded material about that. "
                "Try asking about a topic covered in your course."
            )
        else:
            top = chunks[0]
            snippet = " ".join(top.text.split()[:60])
            text = (
                f"Based on the material: {snippet}...\n\n"
                f"In short — this connects to your question about "
                f'"{message.strip()[:80]}". See the cited source for detail.'
            )
        # simulate streaming
        for word in text.split(" "):
            yield word + " "
        result.usage = Usage(
            cached_input_tokens=800, uncached_input_tokens=120, output_tokens=len(text.split())
        )

    # ------------------------------------------------------------------ #
    # Gemini backend (OpenAI-compatible endpoint)
    # ------------------------------------------------------------------ #
    def _gemini_kwargs(self) -> dict:
        # `reasoning_effort` is only valid on Gemini 2.5 (thinking) models;
        # sending it to 2.0 / non-thinking models errors. Turn thinking off
        # where supported so the classifier and JSON calls stay fast.
        if "2.5" in self.settings.gemini_model:
            return {"reasoning_effort": "none"}
        return {}

    def _gemini_messages(self, system: str, context: str, history: list[dict], user: str):
        msgs = [{"role": "system", "content": system + "\n\nCourse context:\n" + context}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": user})
        return msgs

    def _gemini_chat(
        self, message: str, context_chunks: list[Chunk], history: list[dict], result: ChatResult
    ) -> Iterator[str]:
        context = _format_context(context_chunks)
        stream = self._gemini.chat.completions.create(
            model=self.settings.gemini_model,
            messages=self._gemini_messages(TUTOR_SYSTEM, context, history, message),
            max_tokens=1024,
            stream=True,
            stream_options={"include_usage": True},
            **self._gemini_kwargs(),
        )
        usage = None
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
            if getattr(chunk, "usage", None):
                usage = chunk.usage
        if usage:
            cached = 0
            details = getattr(usage, "prompt_tokens_details", None)
            if details is not None:
                cached = getattr(details, "cached_tokens", 0) or 0
            result.usage = Usage(
                cached_input_tokens=cached,
                uncached_input_tokens=(usage.prompt_tokens or 0) - cached,
                output_tokens=usage.completion_tokens or 0,
            )

    def _gemini_json(self, system: str, user: str, schema):
        """Structured output via Gemini JSON mode + Pydantic validation,
        reject-and-retry once."""
        last_err = None
        for _ in range(2):
            resp = self._gemini.chat.completions.create(
                model=self.settings.gemini_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
                **self._gemini_kwargs(),
            )
            raw = resp.choices[0].message.content or ""
            try:
                return schema.model_validate(json.loads(raw))
            except Exception as e:
                last_err = str(e)
                user = user + f"\n\nYour previous output was invalid: {e}. Return valid JSON."
        raise ValueError(f"structured output failed validation twice: {last_err}")

    # ------------------------------------------------------------------ #
    # Off-syllabus classifier
    # ------------------------------------------------------------------ #
    def _mock_off_syllabus(self, question: str, context_chunks: list[Chunk]) -> bool:
        # Heuristic: off-syllabus if the question's content words barely overlap
        # the retrieved material (robust to the hashing fallback, which gives
        # every pair a small non-zero similarity).
        if not context_chunks:
            return True
        q_words = {w for w in re.findall(r"[a-z]{4,}", question.lower())} - _STOPWORDS
        if not q_words:
            return False
        corpus_words = set(
            re.findall(r"[a-z]{4,}", " ".join(c.text for c in context_chunks).lower())
        )
        overlap = len(q_words & corpus_words) / len(q_words)
        return overlap < 0.34

    @traced("is_off_syllabus", run_type="llm")
    def is_off_syllabus(self, question: str, context_chunks: list[Chunk]) -> bool:
        if self.provider == "mock":
            return self._mock_off_syllabus(question, context_chunks)

        context = _format_context(context_chunks) or "(no relevant context found)"

        if self.provider == "gemini":
            try:
                resp = self._gemini.chat.completions.create(
                    model=self.settings.gemini_model,
                    max_tokens=8,
                    messages=[
                        {"role": "system", "content": OFF_SYLLABUS_CLASSIFIER},
                        {"role": "user", "content": f"COURSE CONTEXT:\n{context}\n\nQUESTION: {question}"},
                    ],
                    **self._gemini_kwargs(),
                )
                return (resp.choices[0].message.content or "").strip().lower().startswith("no")
            except Exception:
                if self.settings.llm_strict:
                    raise
                # Quota/error: fall back to the lexical-overlap heuristic.
                return self._mock_off_syllabus(question, context_chunks)

        resp = self._client.messages.create(
            model=self.settings.tutor_model,
            max_tokens=8,
            system=OFF_SYLLABUS_CLASSIFIER,
            messages=[
                {
                    "role": "user",
                    "content": f"COURSE CONTEXT:\n{context}\n\nQUESTION: {question}",
                }
            ],
        )
        answer = "".join(
            b.text for b in resp.content if getattr(b, "type", "") == "text"
        ).strip().lower()
        return answer.startswith("no")

    # ------------------------------------------------------------------ #
    # Quiz generation (structured output)
    # ------------------------------------------------------------------ #
    @traced("generate_quiz", run_type="llm")
    def generate_quiz(
        self, topic: str, difficulty: str, n: int, context_chunks: list[Chunk]
    ) -> Quiz:
        if self.provider == "mock":
            return self._mock_quiz(topic, difficulty, n, context_chunks)

        context = _format_context(context_chunks)
        user = (
            f"Topic: {topic}\nDifficulty: {difficulty}\nNumber of questions: {n}\n\n"
            f"Course material:\n{context}"
        )
        if self.provider == "gemini":
            hint = (
                user
                + "\n\nReturn JSON matching this schema: "
                + json.dumps(QUIZ_TOOL["input_schema"])
                + '. answer_index is the 0-based index of the correct choice.'
            )
            try:
                return self._gemini_json(QUIZ_SYSTEM, hint, Quiz)
            except Exception:
                if self.settings.llm_strict:
                    raise
                return self._mock_quiz(topic, difficulty, n, context_chunks)

        return self._tool_call(system=QUIZ_SYSTEM, user=user, tool=QUIZ_TOOL, schema=Quiz)

    def _mock_quiz(
        self, topic: str, difficulty: str, n: int, chunks: list[Chunk]
    ) -> Quiz:
        from .models import QuizQuestion

        concepts = _extract_concepts(chunks) or [topic or "the material"]
        questions = []
        for i in range(max(1, n)):
            concept = concepts[i % len(concepts)]
            correct = f"The definition involving {concept}"
            distractors = [
                f"An unrelated claim about {concepts[(i + 1) % len(concepts)]}",
                "None of the above",
                f"A common misreading of {concept}",
            ]
            choices = [correct] + distractors
            questions.append(
                QuizQuestion(
                    id=str(uuid.uuid4()),
                    concept=concept,
                    prompt=f"Which statement best describes {concept}?",
                    choices=choices,
                    answer_index=0,
                    difficulty=difficulty,  # type: ignore[arg-type]
                    rationale=f"{concept} is defined this way in the material.",
                    source_chunk_ids=[c.id for c in chunks[:1]],
                )
            )
        return Quiz(topic=topic or "Course review", questions=questions)

    # ------------------------------------------------------------------ #
    # Grading (structured output)
    # ------------------------------------------------------------------ #
    @traced("grade_answer", run_type="llm")
    def grade_answer(
        self,
        question_id: str,
        question_prompt: str,
        choices: list[str],
        chosen_index: int,
        correct_index: int,
        rationale: str,
        concept: str,
        context_chunks: list[Chunk],
    ) -> Grade:
        is_correct = chosen_index == correct_index
        if self.provider == "mock":
            return self._mock_grade(
                question_id, is_correct, concept, choices, correct_index, rationale
            )

        context = _format_context(context_chunks)
        chosen = choices[chosen_index] if 0 <= chosen_index < len(choices) else "(none)"
        correct = choices[correct_index] if 0 <= correct_index < len(choices) else "(none)"
        user = (
            f"Question ({question_id}): {question_prompt}\n"
            f"Learner chose: {chosen}\n"
            f"Correct answer: {correct}\n"
            f"Rationale: {rationale}\n"
            f"The learner was {'CORRECT' if is_correct else 'INCORRECT'}.\n\n"
            f"Course material:\n{context}"
        )
        if self.provider == "gemini":
            hint = (
                user
                + "\n\nReturn JSON matching this schema: "
                + json.dumps(GRADE_TOOL["input_schema"])
            )
            try:
                grade = self._gemini_json(GRADE_SYSTEM, hint, Grade)
            except Exception:
                if self.settings.llm_strict:
                    raise
                grade = self._mock_grade(
                    question_id, is_correct, concept, choices, correct_index, rationale
                )
        else:
            grade = self._tool_call(
                system=GRADE_SYSTEM, user=user, tool=GRADE_TOOL, schema=Grade
            )
        # Never let the model overrule the deterministic correctness check.
        grade.correct = is_correct
        grade.question_id = question_id
        return grade

    def _mock_grade(
        self,
        question_id: str,
        is_correct: bool,
        concept: str,
        choices: list[str],
        correct_index: int,
        rationale: str,
    ) -> Grade:
        if is_correct:
            return Grade(
                question_id=question_id,
                correct=True,
                feedback=f"Correct. {rationale}",
            )
        correct = choices[correct_index] if 0 <= correct_index < len(choices) else ""
        return Grade(
            question_id=question_id,
            correct=False,
            misconception_tag=f"confused-{re.sub(r'[^a-z]+', '-', concept.lower())[:20]}",
            feedback=(
                f"Not quite. The correct answer was: \"{correct}\". {rationale} "
                f"Revisit the section on {concept}."
            ),
            followup_prompt=f"In your own words, what is {concept}?",
        )

    # ------------------------------------------------------------------ #
    # Shared: forced tool call with reject-and-retry-once
    # ------------------------------------------------------------------ #
    def _tool_call(self, system: str, user: str, tool: dict, schema):
        last_err = None
        for attempt in range(2):
            resp = self._client.messages.create(
                model=self.settings.tutor_model,
                max_tokens=2048,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
                messages=[{"role": "user", "content": user}],
            )
            block = next(
                (b for b in resp.content if getattr(b, "type", "") == "tool_use"), None
            )
            if block is None:
                last_err = "model did not call the tool"
                continue
            try:
                return schema.model_validate(block.input)
            except Exception as e:  # validation failure -> retry once, then fail visibly
                last_err = str(e)
                user = (
                    user
                    + f"\n\nYour previous output failed schema validation: {e}. "
                    "Return a valid response."
                )
        raise ValueError(f"structured output failed validation twice: {last_err}")


def _extract_concepts(chunks: list[Chunk], limit: int = 6) -> list[str]:
    """Cheap keyword extraction for the mock quiz: capitalised phrases and
    frequent multi-word noun-ish terms."""
    text = " ".join(c.text for c in chunks)
    caps = re.findall(r"\b([A-Z][a-z]+(?: [A-Z][a-z]+){0,2})\b", text)
    # Skip generic heading/title words that aren't real concepts.
    skip = {
        "introduction", "sample", "course", "chapter", "section", "overview",
        "summary", "each", "common", "good", "high", "the",
    }
    seen, out = set(), []
    for phrase in caps:
        key = phrase.lower()
        # Prefer multi-word terms; only keep a single word if it isn't generic.
        if key in seen or len(phrase) <= 3 or key in skip:
            continue
        seen.add(key)
        out.append(phrase)
        if len(out) >= limit:
            break
    return out


_llm: Optional[LLM] = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM()
    return _llm
