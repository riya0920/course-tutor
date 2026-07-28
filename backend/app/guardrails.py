"""Guardrails layer.

Three checks, toggled as a group by GUARDRAILS_ENABLED so the eval harness can
produce OFF vs ON baselines from the same corpus:

1. Input: off-syllabus detection (cheap classifier). Off-syllabus -> redirect.
2. Output schema: Pydantic validation (enforced in llm.py at the tool boundary).
3. Grounding: `lookup_source` must return a chunk above a similarity floor for
   the answer to count as supported.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import rag
from .config import get_settings
from .llm import get_llm
from .models import Chunk


@dataclass
class InputCheck:
    off_syllabus: bool
    reason: str = ""


def check_input(session_id: str, question: str, chunks: list[Chunk]) -> InputCheck:
    settings = get_settings()
    if not settings.guardrails_enabled:
        return InputCheck(off_syllabus=False)
    if get_llm().is_off_syllabus(question, chunks):
        return InputCheck(
            off_syllabus=True,
            reason="This question doesn't appear to be covered by the uploaded material.",
        )
    return InputCheck(off_syllabus=False)


def lookup_source(session_id: str, claim: str) -> list[Chunk]:
    """Grounding verification / citation power tool: retrieve the chunks that
    best support a claim, above the similarity floor."""
    settings = get_settings()
    hits = rag.retrieve(session_id, claim, k=settings.retrieve_k)
    return [c for c in hits if c.score >= settings.grounding_floor]


def is_grounded(session_id: str, claim: str) -> bool:
    if not get_settings().guardrails_enabled:
        return True
    return len(lookup_source(session_id, claim)) > 0
