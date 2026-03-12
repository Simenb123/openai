from __future__ import annotations

import json
from pathlib import Path

from rag_assistant.kildebibliotek import Relation
from rag_assistant.relation_io import (
    export_relations_to_csv,
    export_relations_to_json,
    import_relations_from_csv,
    import_relations_from_json,
)


def _keys(rels: list[Relation]) -> set[str]:
    return {r.key() for r in rels}


def test_csv_roundtrip_semicolon(tmp_path: Path):
    rels = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1", note="n1"),
        Relation(from_id="ISA-230", to_id="RL", relation_type="RELATES_TO", from_anchor="P8", to_anchor="§1-1"),
    ]
    p = tmp_path / "rels.csv"
    n = export_relations_to_csv(rels, p, delimiter=";")
    assert n == 2
    res = import_relations_from_csv(p)
    assert not res.warnings
    assert _keys(res.relations) == _keys(rels)


def test_csv_import_accepts_norwegian_headers(tmp_path: Path):
    p = tmp_path / "rels.csv"
    content = """fra_id;fra_anker;relasjonstype;til_id;til_anker;notat
RL;§1;IMPLEMENTS;RF;§1-1;hjemmel
"""
    p.write_text(content, encoding="utf-8-sig")
    res = import_relations_from_csv(p)
    assert len(res.relations) == 1
    r = res.relations[0]
    assert r.from_id == "RL"
    assert r.to_id == "RF"
    assert r.relation_type == "IMPLEMENTS"
    assert r.from_anchor == "§1"
    assert r.to_anchor == "§1-1"
    assert r.note == "hjemmel"


def test_json_roundtrip_list(tmp_path: Path):
    rels = [
        Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="P1", to_anchor="P2", note="x"),
    ]
    p = tmp_path / "rels.json"
    n = export_relations_to_json(rels, p)
    assert n == 1
    res = import_relations_from_json(p)
    assert not res.warnings
    assert _keys(res.relations) == _keys(rels)


def test_json_import_accepts_object_with_relations_key(tmp_path: Path):
    p = tmp_path / "rels.json"
    payload = {
        "relations": [
            {"from_id": "RL", "to_id": "RF", "relation_type": "RELATES_TO", "from_anchor": "§1", "to_anchor": "§1-1"}
        ]
    }
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    res = import_relations_from_json(p)
    assert len(res.relations) == 1
    assert res.relations[0].from_id == "RL"
