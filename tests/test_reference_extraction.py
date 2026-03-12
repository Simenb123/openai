from __future__ import annotations

from rag_assistant.reference_extraction import extract_all_legal_anchors, extract_all_standard_anchors, make_snippet


def test_extract_all_legal_anchors_with_ledd_and_bokstav():
    txt = "Se § 1-1 (1) bokstav a og § 2-3."
    refs = extract_all_legal_anchors(txt)
    anchors = [r.anchor for r in refs]
    assert "§1-1(1)[a]" in anchors
    assert "§2-3" in anchors


def test_extract_all_standard_anchors():
    txt = "Se punkt 8 og P9 samt A1."
    refs = extract_all_standard_anchors(txt)
    anchors = [r.anchor for r in refs]
    assert "P8" in anchors
    assert "P9" in anchors
    assert "A1" in anchors


def test_make_snippet_limits_length():
    txt = "x" * 1000 + " § 1-1 (1) bokstav a " + "y" * 1000
    refs = extract_all_legal_anchors(txt)
    assert refs
    snip = make_snippet(txt, refs[0].start, refs[0].end, max_len=120)
    assert len(snip) <= 120
