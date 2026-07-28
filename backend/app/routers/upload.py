"""POST /upload — parse, chunk, embed and index a course document."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, UploadFile

from .. import db, rag

router = APIRouter()

_MAX_BYTES = 20 * 1024 * 1024  # 20 MB


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    session_id: str = Form(default=""),
):
    session_id = session_id or f"sess_{uuid.uuid4().hex[:12]}"
    data = await file.read()
    if len(data) > _MAX_BYTES:
        return {"error": "file too large (max 20MB)"}, 413

    db.ensure_session(session_id)
    n_chunks = rag.index_document(session_id, file.filename or "document", data)
    db.set_session_corpus(session_id, file.filename or "document")

    return {
        "session_id": session_id,
        "filename": file.filename,
        "chunks_indexed": n_chunks,
    }
