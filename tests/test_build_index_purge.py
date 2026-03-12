# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import rag_assistant.build_index as build_index
from rag_assistant.kildebibliotek import Library, Source
from rag_assistant.settings_profiles import Settings


def test_build_index_from_library_purges_existing_by_source_id(monkeypatch, tmp_path: Path) -> None:
    # Lag en enkel kildefil
    f = tmp_path / "revisorloven"
    f.write_text("§ 1-1 Virkeområde\nDette er en test.", encoding="utf-8")

    lib = Library()
    lib.upsert_source(Source(id="RL", title="Revisorloven", doc_type="LOV", files=[str(f)]))

    calls: Dict[str, Any] = {"delete_where": [], "delete_all": 0, "upsert": 0}

    fake_col = object()

    monkeypatch.setattr(build_index, "get_or_create_collection", lambda **kwargs: fake_col)

    def fake_delete_where(col, where):  # type: ignore[no-untyped-def]
        assert col is fake_col
        calls["delete_where"].append(where)
        return 0

    def fake_delete_all(col):  # type: ignore[no-untyped-def]
        assert col is fake_col
        calls["delete_all"] += 1
        return 0

    def fake_upsert(col, docs, metas, ids):  # type: ignore[no-untyped-def]
        assert col is fake_col
        calls["upsert"] += len(docs)

    monkeypatch.setattr(build_index, "delete_where", fake_delete_where)
    monkeypatch.setattr(build_index, "delete_all_documents", fake_delete_all)
    monkeypatch.setattr(build_index, "upsert_documents", fake_upsert)

    n = build_index.build_index_from_library(
        lib,
        settings=Settings(db_path="x", collection="y"),
        chunk_size=200,
        chunk_overlap=0,
        purge_existing=True,
        wipe_collection=False,
    )

    assert n >= 1
    assert calls["delete_all"] == 0
    assert calls["delete_where"] == [{"source_id": "RL"}]
    assert calls["upsert"] == n


def test_build_index_from_library_wipe_collection(monkeypatch, tmp_path: Path) -> None:
    f = tmp_path / "revisorloven"
    f.write_text("§ 1-1 Virkeområde\nDette er en test.", encoding="utf-8")

    lib = Library()
    lib.upsert_source(Source(id="RL", title="Revisorloven", doc_type="LOV", files=[str(f)]))

    calls: Dict[str, Any] = {"delete_where": [], "delete_all": 0}

    fake_col = object()
    monkeypatch.setattr(build_index, "get_or_create_collection", lambda **kwargs: fake_col)

    def fake_delete_where(col, where):  # type: ignore[no-untyped-def]
        calls["delete_where"].append(where)
        return 0

    def fake_delete_all(col):  # type: ignore[no-untyped-def]
        calls["delete_all"] += 1
        return 0

    monkeypatch.setattr(build_index, "delete_where", fake_delete_where)
    monkeypatch.setattr(build_index, "delete_all_documents", fake_delete_all)
    monkeypatch.setattr(build_index, "upsert_documents", lambda *a, **k: None)

    _ = build_index.build_index_from_library(
        lib,
        settings=Settings(db_path="x", collection="y"),
        chunk_size=200,
        chunk_overlap=0,
        wipe_collection=True,
    )

    assert calls["delete_all"] == 1
    assert calls["delete_where"] == []
