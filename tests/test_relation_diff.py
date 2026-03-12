from __future__ import annotations

from rag_assistant.kildebibliotek import Relation
from rag_assistant.relation_diff import compute_relation_diff, compute_relation_diff_summary


def test_diff_counts_added_updated_removed():
    existing = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="a"),
        Relation(from_id="ISA-230", to_id="RL", relation_type="RELATES_TO", from_anchor="P8", to_anchor="§1"),
    ]

    incoming = [
        # unchanged (note None -> None)
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        # updated (note changes)
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="b"),
        # added
        Relation(from_id="RL", to_id="RF", relation_type="IMPLEMENTS", from_anchor="§3", to_anchor="§3-1"),
    ]

    d = compute_relation_diff_summary(existing, incoming, sample_limit=10)
    assert d.existing_total == 3
    assert d.incoming_total == 3
    assert d.incoming_unique == 3
    assert d.added == 1
    assert d.updated == 1
    assert d.unchanged == 1
    # removed: ISA-230->RL P8->§1 is not in incoming
    assert d.removed == 1


def test_diff_dedupes_by_key_keeps_last():
    existing = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="a"),
    ]

    incoming = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="b"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="c"),
    ]

    d = compute_relation_diff_summary(existing, incoming)
    # incoming_total counts rows, incoming_unique counts deduped
    assert d.incoming_total == 2
    assert d.incoming_unique == 1
    assert d.updated == 1


def test_compute_relation_diff_returns_lists_and_update_objects():
    existing = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="a"),
    ]
    incoming = [
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"),
        Relation(from_id="RL", to_id="RF", relation_type="RELATES_TO", from_anchor="§2", to_anchor="§2-1", note="b"),
        Relation(from_id="RL", to_id="RF", relation_type="IMPLEMENTS", from_anchor="§3", to_anchor="§3-1"),
    ]

    d = compute_relation_diff(existing, incoming)
    assert d.existing_total == 2
    assert d.incoming_total == 3
    assert d.incoming_unique == 3
    assert len(d.added) == 1
    assert len(d.updated) == 1
    assert len(d.unchanged) == 1
    assert len(d.removed) == 0

    u = d.updated[0]
    assert u.old.note == "a"
    assert u.new.note == "b"
