"""GET /progress/{session_id} — per-concept mastery view."""
from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..models import ProgressReport

router = APIRouter()


@router.get("/progress/{session_id}", response_model=ProgressReport)
async def progress(session_id: str) -> ProgressReport:
    db.ensure_session(session_id)
    return db.get_progress(session_id)
