from __future__ import annotations

from rag_assistant.kildebibliotek import Relation
from rag_assistant.relation_mapping import (
    group_relations_by_from_anchor,
    mapped_from_anchors,
    suggest_target_anchors,
    to_anchors_for_from_anchor,
)


def test_suggest_target_anchors_prefix_for_law_to_regulation():
    # Fra lovparagraf §1 og til-ankere i forskrift
    targets = ["§1-1", "§1-2", "§2-1", "§10-1"]
    s = suggest_target_anchors("§1", targets)
    # Skal prioritere §1-... først (prefix)
    assert "§1-1" in s
    assert "§1-2" in s
    # Skal ikke feile
    assert isinstance(s, list)


def test_suggest_target_anchors_hierarchy_for_subanchor():
    targets = ["§1-1", "§1-1(1)", "§1-1(1)[a]", "§1-1(2)"]
    s = suggest_target_anchors("§1-1(1)[a]", targets)
    # Eksakt match først
    assert s[0] == "§1-1(1)[a]"
    # Foreldre bør også være med
    assert "§1-1(1)" in s
    assert "§1-1" in s


def test_suggest_target_anchors_standard_points():
    targets = ["P8", "P8.1", "P9", "A1"]
    s = suggest_target_anchors("P8", targets)
    assert "P8" in s
    assert "P8.1" in s


def test_group_relations_by_from_anchor_filters_pair_and_requires_anchors():
    rels = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-2"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO"),  # doc-level
        Relation(from_id="X", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
    ]

    grouped = group_relations_by_from_anchor(rels, "RL", "RF")
    assert set(grouped.keys()) == {"§1"}
    assert len(grouped["§1"]) == 2


def test_mapped_from_anchors_returns_set():
    rels = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO"),  # doc-level
    ]
    s = mapped_from_anchors(rels, "RL", "RF")
    assert s == {"§1", "§2"}


def test_to_anchors_for_from_anchor_dedupes_and_preserves_order():
    rels = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-2"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-2"),
    ]
    out = to_anchors_for_from_anchor(rels, "RL", "RF", "§ 1")
    assert out == ["§1-2", "§1-1"]
