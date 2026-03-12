from __future__ import annotations

from rag_assistant.anchor_validation import check_anchor


def test_check_anchor_ok_when_no_anchor() -> None:
    inv = {"version": 1, "generated_at": None, "sources": {"RL": {"anchors": ["§1"]}}}
    res = check_anchor(inv, "RL", None)
    assert res.status == "ok"
    assert res.normalized_anchor is None


def test_check_anchor_missing_inventory() -> None:
    inv = {"version": 1, "generated_at": None, "sources": {}}
    res = check_anchor(inv, "RL", "§1")
    assert res.status == "missing_inventory"
    assert res.normalized_anchor == "§1"


def test_check_anchor_empty_inventory() -> None:
    inv = {"version": 1, "generated_at": None, "sources": {"RL": {"anchors": []}}}
    res = check_anchor(inv, "RL", "§1")
    assert res.status == "empty_inventory"


def test_check_anchor_unknown_anchor_gets_suggestions() -> None:
    inv = {
        "version": 1,
        "generated_at": None,
        "sources": {"RL": {"anchors": ["§1", "§1-1", "§2", "§10"]}},
    }
    res = check_anchor(inv, "RL", "§1-2")
    assert res.status == "unknown_anchor"
    assert res.normalized_anchor == "§1-2"
    assert res.anchors_count == 4
    # forslag bør være relatert til §1
    assert "§1" in res.suggestions


def test_check_anchor_ok_when_anchor_is_in_inventory_and_normalized() -> None:
    inv = {
        "version": 1,
        "generated_at": None,
        "sources": {"ISA-230": {"anchors": ["P8", "A1"]}},
    }
    res = check_anchor(inv, "ISA-230", "8")
    assert res.status == "ok"
    assert res.normalized_anchor == "P8"


def test_check_anchor_ok_when_legal_ledd_anchor_is_normalized() -> None:
    inv = {
        "version": 1,
        "generated_at": None,
        "sources": {"RL": {"anchors": ["§1-1(1)", "§1-1(1)[a]"]}},
    }
    res = check_anchor(inv, "RL", "§ 1-1 (1)")
    assert res.status == "ok"
    assert res.normalized_anchor == "§1-1(1)"

    res2 = check_anchor(inv, "RL", "§ 1-1 (1) [A]")
    assert res2.status == "ok"
    assert res2.normalized_anchor == "§1-1(1)[a]"
