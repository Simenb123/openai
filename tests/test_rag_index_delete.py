# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

import rag_assistant.rag_index as rag_index


class DeleteWhereOkCollection:
    def __init__(self) -> None:
        self.delete_calls: List[Dict[str, Any]] = []
        self.get_calls: List[Dict[str, Any]] = []

    def delete(self, **kwargs):  # type: ignore[no-untyped-def]
        self.delete_calls.append(kwargs)

    def get(self, **kwargs):  # type: ignore[no-untyped-def]
        self.get_calls.append(kwargs)
        raise AssertionError("get() skal ikke kalles når delete(where=...) fungerer")


def test_delete_where_prefers_collection_delete_where() -> None:
    col = DeleteWhereOkCollection()
    n = rag_index.delete_where(col, {"source_id": "RL"})

    assert n == 0
    assert len(col.delete_calls) == 1
    assert col.delete_calls[0].get("where") == {"source_id": "RL"}
    assert col.get_calls == []


class DeleteWhereFailsCollection:
    """Simulerer en Chroma-versjon der collection.delete(where=...) feiler (TypeError).

    Da skal vi fallbacke til get() + delete(ids=...).
    """

    def __init__(self) -> None:
        self.delete_calls: List[Dict[str, Any]] = []
        self.get_calls: List[Dict[str, Any]] = []
        self._returned_once = False

    def delete(self, **kwargs):  # type: ignore[no-untyped-def]
        # Første forsøk: delete(where=...) gir TypeError
        if "where" in kwargs:
            raise TypeError("delete(where=...) ikke støttet")
        self.delete_calls.append(kwargs)

    def get(self, **kwargs):  # type: ignore[no-untyped-def]
        self.get_calls.append(kwargs)

        # Første page -> returner ids
        if not self._returned_once:
            self._returned_once = True
            return {"ids": ["a", "b", "c"]}

        # Neste page -> tom
        return {"ids": []}


def test_delete_where_falls_back_to_get_and_delete_ids() -> None:
    col = DeleteWhereFailsCollection()
    n = rag_index.delete_where(col, {"source_id": "RL"})

    assert n == 3

    # Skal ha forsøkt delete(where=...), men det feilet og blir ikke registrert i delete_calls
    # (TypeError blir kastet og håndtert)

    assert len(col.get_calls) >= 1
    # Siste steg: delete(ids=[...])
    assert len(col.delete_calls) == 1
    assert col.delete_calls[0].get("ids") == ["a", "b", "c"]


class DeleteAllCollection:
    def __init__(self) -> None:
        self.delete_calls: List[Dict[str, Any]] = []

    def delete(self, **kwargs):  # type: ignore[no-untyped-def]
        self.delete_calls.append(kwargs)

    def get(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("get() skal ikke kalles når delete(where={}) fungerer")


def test_delete_all_documents_uses_where_empty_dict() -> None:
    col = DeleteAllCollection()
    n = rag_index.delete_all_documents(col)
    assert n == 0
    assert col.delete_calls and col.delete_calls[0].get("where") == {}
