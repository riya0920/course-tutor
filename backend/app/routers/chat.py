"""POST /chat — retrieval-augmented tutor chat over SSE.

Flow per turn:
  retrieve top-k -> input guardrail (off-syllabus) -> stream answer ->
  grounding check -> emit a final `meta` event with citations + telemetry.

SSE event shapes:
  data: {"type": "token", "text": "..."}
  data: {"type": "meta",  ...ChatMeta}
  data: {"type": "done"}
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from .. import db, guardrails, rag
from ..config import get_settings
from ..llm import ChatResult, get_llm
from ..models import ChatMeta, ChatRequest, Citation

router = APIRouter()

# In-memory conversation history, keyed by session (single-user demo).
_HISTORY: dict[str, list[dict]] = {}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    settings = get_settings()
    db.ensure_session(req.session_id)
    history = _HISTORY.setdefault(req.session_id, [])

    def gen():
        t0 = time.time()
        chunks = rag.retrieve(req.session_id, req.message)

        # --- input guardrail -------------------------------------------
        check = guardrails.check_input(req.session_id, req.message, chunks)
        if check.blocked or check.off_syllabus:
            if check.blocked:
                message = check.reason
            else:
                message = (
                    "That looks outside this course's material. "
                    + check.reason
                    + " Try asking about something covered in your uploaded document."
                )
            for word in message.split(" "):
                yield _sse({"type": "token", "text": word + " "})
            meta = ChatMeta(
                citations=[],
                grounded=False,
                off_syllabus=check.off_syllabus,
                model=get_llm().model,
                ttft_ms=(time.time() - t0) * 1000,
            )
            yield _sse({"type": "meta", **meta.model_dump()})
            yield _sse({"type": "done"})
            return

        # --- stream the grounded answer --------------------------------
        result = ChatResult()
        answer_parts: list[str] = []
        ttft_ms = None
        for text in get_llm().stream_chat(
            req.message, chunks, history, result, session_id=req.session_id
        ):
            if ttft_ms is None:
                ttft_ms = (time.time() - t0) * 1000
            answer_parts.append(text)
            yield _sse({"type": "token", "text": text})

        answer = "".join(answer_parts)
        history.append({"role": "user", "content": req.message})
        history.append({"role": "assistant", "content": answer})

        # --- grounding check + citations -------------------------------
        supporting = guardrails.lookup_source(req.session_id, answer or req.message)
        grounded = len(supporting) > 0 or not settings.guardrails_enabled
        citations = [
            Citation(
                chunk_id=c.id,
                source=c.source,
                page=c.page,
                quote=" ".join(c.text.split()[:30]),
            )
            for c in supporting[:3]
        ]

        meta = ChatMeta(
            citations=citations,
            grounded=grounded,
            off_syllabus=False,
            cached_input_tokens=result.usage.cached_input_tokens,
            uncached_input_tokens=result.usage.uncached_input_tokens,
            output_tokens=result.usage.output_tokens,
            ttft_ms=ttft_ms,
            model=get_llm().model,
        )
        yield _sse({"type": "meta", **meta.model_dump()})
        yield _sse({"type": "done"})

    return StreamingResponse(gen(), media_type="text/event-stream")
