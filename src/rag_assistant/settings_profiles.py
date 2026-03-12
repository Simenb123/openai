from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Settings:
    """Samlet konfigurasjon.

    Verdier kan overstyres via miljøvariabler (evt. .env).
    """

    db_path: str = "ragdb"
    collection: str = "revisjon"

    # OpenAI
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    base_url: Optional[str] = None


def load_settings() -> Settings:
    """Leser settings fra miljøvariabler (med defaults)."""
    return Settings(
        db_path=os.getenv("RAG_DB_PATH", "ragdb"),
        collection=os.getenv("RAG_COLLECTION", "revisjon"),
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
        embedding_model=os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def apply_env(settings: Settings, *, override: bool = False) -> None:
    """Setter miljøvariabler ut fra Settings.

    Vi setter ikke OPENAI_API_KEY her (skal ligge i .env / miljø).
    """

    def _set(key: str, value: Optional[str]) -> None:
        if value is None:
            return
        if override or not os.getenv(key):
            os.environ[key] = value

    _set("RAG_DB_PATH", settings.db_path)
    _set("RAG_COLLECTION", settings.collection)
    _set("OPENAI_CHAT_MODEL", settings.chat_model)
    _set("OPENAI_EMBED_MODEL", settings.embedding_model)
    _set("OPENAI_BASE_URL", settings.base_url)
