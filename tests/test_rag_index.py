# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from rag_assistant.rag_index import OpenAIEmbeddingFunction, add_documents


def test_openai_embedding_function_has_name_attribute() -> None:
    # vi gir en dummy api_key slik at klassen ikke leser fra miljø
    ef = OpenAIEmbeddingFunction(api_key="DUMMY", model_name="test-model")
    assert hasattr(ef, "name")
    assert ef.name == "test-model"


def test_add_documents_prefers_upsert_when_available() -> None:
    calls: Dict[str, Any] = {}

    class DummyCol:
        def upsert(self, **kwargs: Any) -> None:
            calls["method"] = "upsert"
            calls["kwargs"] = kwargs

        def add(self, **kwargs: Any) -> None:  # pragma: no cover - skal ikke brukes
            calls["method"] = "add"
            calls["kwargs"] = kwargs

    items = [
        {"id": "A:chunk-0", "text": "hei", "metadata": {"source_path": "a.txt"}},
        {"id": "A:chunk-1", "text": "hallo", "metadata": {"source_path": "a.txt"}},
    ]
    add_documents(DummyCol(), items)  # type: ignore[arg-type]

    assert calls["method"] == "upsert"
    assert calls["kwargs"]["ids"] == ["A:chunk-0", "A:chunk-1"]
    assert calls["kwargs"]["documents"] == ["hei", "hallo"]
    assert isinstance(calls["kwargs"]["metadatas"], list)
