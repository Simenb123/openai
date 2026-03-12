from __future__ import annotations

from rag_assistant.gui.anchor_picker import filter_anchors


def test_filter_anchors_empty_query_returns_first_n() -> None:
    anchors = [f"§{i}" for i in range(1, 5000)]
    out = filter_anchors(anchors, "", max_results=10)
    assert out == anchors[:10]


def test_filter_anchors_ignores_whitespace_and_case() -> None:
    anchors = ["§1-1", "§2", "P8", "A1"]
    assert filter_anchors(anchors, "§ 1", max_results=100) == ["§1-1"]
    assert filter_anchors(anchors, "p8", max_results=100) == ["P8"]


def test_filter_anchors_substring_match() -> None:
    anchors = ["§1", "§10", "§11", "§2"]
    out = filter_anchors(anchors, "1", max_results=100)
    # substring '1' matcher §1, §10, §11
    assert out == ["§1", "§10", "§11"]
