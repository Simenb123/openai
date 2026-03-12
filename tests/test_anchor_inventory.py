from __future__ import annotations

from pathlib import Path

from rag_assistant.anchor_inventory import (
    compute_anchor_inventory_from_items,
    inventory_path_for_library,
    load_anchor_inventory,
    save_anchor_inventory,
    update_anchor_inventory_file,
)
from rag_assistant.build_index import BuildItem


def test_inventory_path_for_library_changes_suffix(tmp_path: Path) -> None:
    p = tmp_path / "kildebibliotek.json"
    assert inventory_path_for_library(p).name == "kildebibliotek.anchors.json"


def test_compute_anchor_inventory_sorts_and_normalizes() -> None:
    items = [
        BuildItem(id="1", text="x", metadata={"source_id": "ISA-230", "source_title": "ISA 230", "doc_type": "ISA", "anchor": "8"}),
        BuildItem(id="2", text="y", metadata={"source_id": "ISA-230", "source_title": "ISA 230", "doc_type": "ISA", "anchor": "P1"}),
        BuildItem(id="3", text="z", metadata={"source_id": "ISA-230", "source_title": "ISA 230", "doc_type": "ISA", "anchor": "A2"}),
        BuildItem(id="4", text="z", metadata={"source_id": "ISA-230", "source_title": "ISA 230", "doc_type": "ISA", "anchor": "A1"}),
        BuildItem(id="5", text="z", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§ 1-1"}),
        BuildItem(id="6", text="z", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§1"}),
    ]

    inv = compute_anchor_inventory_from_items(items)
    assert "ISA-230" in inv
    assert "RL" in inv

    # "8" normaliseres til P8
    assert inv["ISA-230"]["anchors"] == ["P1", "P8", "A1", "A2"]
    # § sorteres og normaliseres ("§ 1-1" -> "§1-1")
    assert inv["RL"]["anchors"] == ["§1", "§1-1"]


def test_compute_anchor_inventory_handles_legal_ledd_and_bokstav() -> None:
    items = [
        BuildItem(id="1", text="x", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§ 1-1"}),
        BuildItem(id="2", text="x", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§ 1-1 (1)"}),
        BuildItem(id="3", text="x", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§1-1(1)a"}),
        BuildItem(id="4", text="x", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§1-1(2)[B]"}),
    ]

    inv = compute_anchor_inventory_from_items(items)
    anchors = inv["RL"]["anchors"]
    assert anchors == ["§1-1", "§1-1(1)", "§1-1(1)[a]", "§1-1(2)[b]"]


def test_update_anchor_inventory_file_merges_and_prunes(tmp_path: Path) -> None:
    inv_path = tmp_path / "kildebibliotek.anchors.json"

    # seed existing inventory med en annen kilde
    seed = {
        "version": 1,
        "generated_at": "2020-01-01T00:00:00Z",
        "sources": {"OLD": {"title": "Old", "doc_type": "OTHER", "anchors": ["X"], "anchor_count": 1}},
    }
    save_anchor_inventory(seed, inv_path)

    items = [
        BuildItem(id="1", text="x", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§1"}),
        BuildItem(id="2", text="y", metadata={"source_id": "RL", "source_title": "Revisorloven", "doc_type": "LOV", "anchor": "§1-1"}),
    ]

    # update uten prune: OLD skal fortsatt være der
    update_anchor_inventory_file(inv_path, items, replace_source_ids=["RL"], prune_to_source_ids=None)
    loaded = load_anchor_inventory(inv_path)
    assert "OLD" in loaded["sources"]
    assert loaded["sources"]["RL"]["anchors"] == ["§1", "§1-1"]

    # update med prune: kun RL skal stå igjen
    update_anchor_inventory_file(inv_path, items, replace_source_ids=["RL"], prune_to_source_ids=["RL"])
    loaded2 = load_anchor_inventory(inv_path)
    assert set(loaded2["sources"].keys()) == {"RL"}
