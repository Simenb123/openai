from __future__ import annotations

import json
from pathlib import Path

import rag_assistant.build_index as build_index
from rag_assistant.anchor_inventory import inventory_path_for_library, load_anchor_inventory
from rag_assistant.settings_profiles import Settings


def test_build_index_from_library_file_writes_anchor_inventory(monkeypatch, tmp_path: Path) -> None:
    # Lag kildefil
    src_file = tmp_path / "revisorloven"
    src_file.write_text("§ 1-1 Virkeområde\nTekst\n\n§ 2 Formål\nMer tekst", encoding="utf-8")

    # Lag library json
    lib_path = tmp_path / "kildebibliotek.json"
    lib_path.write_text(
        json.dumps(
            {
                "version": 1,
                "sources": [
                    {
                        "id": "RL",
                        "title": "Revisorloven",
                        "doc_type": "LOV",
                        "files": [str(src_file)],
                        "tags": ["lov"],
                        "metadata": {},
                    }
                ],
                "relations": [],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # Patch bort Chroma/OpenAI
    fake_col = object()
    monkeypatch.setattr(build_index, "get_or_create_collection", lambda **kwargs: fake_col)
    monkeypatch.setattr(build_index, "upsert_documents", lambda *a, **k: None)
    monkeypatch.setattr(build_index, "delete_all_documents", lambda *a, **k: 0)
    monkeypatch.setattr(build_index, "delete_where", lambda *a, **k: 0)

    n = build_index.build_index_from_library_file(
        lib_path,
        settings=Settings(db_path="x", collection="y"),
        chunk_size=500,
        chunk_overlap=0,
        wipe_collection=True,
    )
    assert n >= 1

    inv_path = inventory_path_for_library(lib_path)
    assert inv_path.exists(), "Forventer at ankerliste ble skrevet"

    inv = load_anchor_inventory(inv_path)
    assert "RL" in inv.get("sources", {})
    anchors = inv["sources"]["RL"]["anchors"]
    assert "§1-1" in anchors
    assert "§2" in anchors
