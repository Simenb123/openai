from __future__ import annotations

from rag_assistant.kildebibliotek import Relation
from rag_assistant.relation_apply import apply_relation_import


def test_apply_merge_patch_preserves_order_and_only_updates_changes():
    r1 = Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1")
    r2 = Relation(
        from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="a"
    )
    existing = [r1, r2]

    incoming = [
        # unchanged
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        # updated note
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="b"),
    ]

    res = apply_relation_import(existing, incoming, mode="merge")
    assert res.mode == "merge"
    assert res.diff.added == []
    assert len(res.diff.updated) == 1

    # same order, r2 note updated
    assert [r.key() for r in res.new_relations] == [r1.key(), r2.key()]
    assert res.new_relations[1].note == "b"


def test_apply_merge_patch_appends_new_relations():
    existing = [
        Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="P1", to_anchor="P2"),
    ]

    incoming = [
        Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="P1", to_anchor="P2"),
        Relation(from_id="A", to_id="B", relation_type="IMPLEMENTS", from_anchor="P3", to_anchor="P4"),
    ]

    res = apply_relation_import(existing, incoming, mode="merge")
    assert len(res.new_relations) == 2
    assert res.new_relations[-1].relation_type == "IMPLEMENTS"


def test_apply_replace_pair_only_affects_that_pair_and_counts_ignored():
    existing = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="ISA-230", to_id="RL", relation_type="RELATES_TO", from_anchor="P8", to_anchor="§1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1"),
    ]

    incoming = [
        # in scope
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1", note="x"),
        # outside scope (should be ignored)
        Relation(from_id="ISA-230", to_id="RL", relation_type="RELATES_TO", from_anchor="P8", to_anchor="§1", note="y"),
    ]

    res = apply_relation_import(existing, incoming, mode="replace", scope_pair=("RL", "RF"))
    assert res.ignored_outside_scope == 1

    # ISA-230->RL relation should remain from existing (not replaced)
    keys = [r.key() for r in res.new_relations]
    assert any(k.startswith("ISA-230|") for k in keys)

    # Only one RL->RF relation should exist after replace in scope
    rl_rf = [r for r in res.new_relations if r.from_id == "RL" and r.to_id == "RF"]
    assert len(rl_rf) == 1
    assert rl_rf[0].note == "x"


def test_apply_replace_global_replaces_all_relations():
    existing = [
        Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="P1", to_anchor="P2"),
        Relation(from_id="X", to_id="Y", relation_type="RELATES_TO", from_anchor="P9", to_anchor="P10"),
    ]

    incoming = [
        Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="P1", to_anchor="P2", note="n"),
    ]

    res = apply_relation_import(existing, incoming, mode="replace")
    assert len(res.new_relations) == 1
    assert res.new_relations[0].from_id == "A"
    assert res.new_relations[0].note == "n"
