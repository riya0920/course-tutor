"""LangSmith tracing, made optional.

If the `langsmith` package is installed and LANGSMITH_API_KEY (or
LANGCHAIN_API_KEY) is set, the `traced` decorator sends runs to LangSmith.
Otherwise it is a transparent no-op, so the app runs the same with or without
tracing configured. Set LANGSMITH_TRACING=true to enable.
"""
from __future__ import annotations

import os
from functools import wraps
from typing import Callable

_ENABLED = os.getenv("LANGSMITH_TRACING", "").lower() == "true" and bool(
    os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY")
)

_traceable = None
if _ENABLED:
    try:  # pragma: no cover - depends on optional dependency + credentials
        from langsmith import traceable as _traceable

        os.environ.setdefault("LANGSMITH_PROJECT", os.getenv("LANGSMITH_PROJECT", "course-tutor"))
    except Exception:
        _traceable = None


def traced(name: str, run_type: str = "llm") -> Callable:
    """Decorator: trace this call in LangSmith when enabled, else pass through."""

    def decorator(fn: Callable) -> Callable:
        if _traceable is not None:  # pragma: no cover
            return _traceable(name=name, run_type=run_type)(fn)

        @wraps(fn)
        def passthrough(*args, **kwargs):
            return fn(*args, **kwargs)

        return passthrough

    return decorator


def tracing_enabled() -> bool:
    return _traceable is not None
