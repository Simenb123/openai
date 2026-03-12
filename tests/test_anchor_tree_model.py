from __future__ import annotations

from rag_assistant.anchor_tree_model import build_tree_edges, filter_anchors_with_context, roots


def test_build_tree_edges_legal_hierarchy():
    anchors = ["§1-1", "§1-1(1)", "§1-1(1)[a]", "§2"]
    edges = build_tree_edges(anchors)

    r = roots(edges)
    assert "§1-1" in r
    assert "§2" in r

    assert "§1-1(1)" in edges.get("§1-1", [])
    assert "§1-1(1)[a]" in edges.get("§1-1(1)", [])


def test_build_tree_edges_standard_hierarchy():
    anchors = ["P1", "P1.2", "P1.2.3", "A1"]
    edges = build_tree_edges(anchors)
    r = roots(edges)
    assert "P1" in r
    assert "A1" in r

    assert "P1.2" in edges.get("P1", [])
    assert "P1.2.3" in edges.get("P1.2", [])


def test_filter_anchors_with_context_includes_parents():
    anchors = ["§1-1", "§1-1(1)", "§1-1(1)[a]", "§2-1"]
    filtered = filter_anchors_with_context(anchors, "1-1(1)[a]")

    # Treffer
    assert "§1-1(1)[a]" in filtered
    # Foreldre inkludert
    assert "§1-1(1)" in filtered
    assert "§1-1" in filtered
    # Ikke-relatert anker kan være fraværende
    assert "§2-1" not in filtered
