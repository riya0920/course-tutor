"""Central configuration, read from the environment.

Nothing here requires an API key to import — the app boots in an offline
`mock` mode when no key is present, so the demo runs with zero setup.

All values are read in ``__init__`` (not at class-definition time), so
``get_settings.cache_clear()`` genuinely re-reads the environment — the eval
harness relies on this to flip ``GUARDRAILS_ENABLED`` between runs.
"""
from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    def __init__(self) -> None:
        # --- LLM -----------------------------------------------------------
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        # Opus 5 by default; set TUTOR_MODEL=claude-sonnet-5 to trade some
        # quality for cost on high-volume workloads.
        self.tutor_model = os.getenv("TUTOR_MODEL", "claude-opus-5")
        self.openai_base_model = os.getenv("OPENAI_BASE_MODEL", "gpt-4o-mini")
        self.finetuned_model = os.getenv("FINETUNED_MODEL", "")

        # --- Retrieval -----------------------------------------------------
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.chunk_tokens = int(os.getenv("CHUNK_TOKENS", "320"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "60"))
        self.retrieve_k = int(os.getenv("RETRIEVE_K", "5"))
        self.grounding_floor = float(os.getenv("GROUNDING_FLOOR", "0.35"))

        # --- Guardrails master switch (eval harness flips this) ------------
        self.guardrails_enabled = os.getenv("GUARDRAILS_ENABLED", "true").lower() == "true"

        # --- Storage -------------------------------------------------------
        self.data_dir = os.getenv("DATA_DIR", os.path.join(os.getcwd(), "data"))
        self.chroma_dir = os.getenv("CHROMA_DIR", "") or os.path.join(self.data_dir, "chroma")
        self.sqlite_path = os.getenv("SQLITE_PATH", "") or os.path.join(self.data_dir, "tutor.db")

        # --- Server --------------------------------------------------------
        self.cors_origins = os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")

        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.chroma_dir, exist_ok=True)

    @property
    def mock_mode(self) -> bool:
        """True when no Anthropic key is configured: the app serves
        deterministic canned responses so it runs end-to-end offline."""
        return not self.anthropic_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
