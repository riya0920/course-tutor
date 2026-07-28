"""POST /explain — restate -> explain -> example -> check-understanding.

Powers the app's "explanation model: base / tuned" toggle (the fine-tuning
component). With no OpenAI key it returns a templated mock so the toggle is
always demoable.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import rag
from ..config import get_settings

router = APIRouter()


class ExplainRequest(BaseModel):
    session_id: str
    concept: str
    model: str = "base"  # "base" | "tuned"


SYSTEM = (
    "You are a course tutor. Explain the concept in four steps: restate the "
    "question, explain the idea, give a concrete example, then ask one "
    "check-understanding question. Ground the explanation in the material."
)


@router.post("/explain")
async def explain(req: ExplainRequest):
    settings = get_settings()
    chunks = rag.retrieve(req.session_id, req.concept, k=3)
    context = "\n\n".join(c.text for c in chunks)

    use_tuned = req.model == "tuned"
    model_name = settings.finetuned_model if use_tuned else settings.openai_base_model

    # Fall back to the mock explanation if OpenAI isn't usable: no key, the
    # tuned model isn't set, or the `openai` package isn't installed.
    try:
        from openai import OpenAI
    except ImportError:
        OpenAI = None

    if (
        OpenAI is None
        or not settings.openai_api_key
        or (use_tuned and not settings.finetuned_model)
    ):
        # Mock explanation following the finetuned structure.
        snippet = " ".join(context.split()[:40]) if context else "the material"
        text = (
            f"Let's break down {req.concept}. "
            f"In short: {snippet}. "
            f"For example, consider a simple case where {req.concept} applies. "
            f"Check yourself: can you state {req.concept} in one sentence?"
        )
        return {
            "concept": req.concept,
            "model": ("tuned" if use_tuned else "base") + " (mock)",
            "explanation": text,
        }

    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Course material:\n{context}\n\nExplain: {req.concept}",
            },
        ],
    )
    return {
        "concept": req.concept,
        "model": model_name,
        "explanation": resp.choices[0].message.content,
    }
