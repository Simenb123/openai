from __future__ import annotations

from rag_assistant.golden_eval import ExpectedAnchor, GoldenCase, evaluate_case_on_chunks
from rag_assistant.rag_bridge import ContextChunk


def test_golden_eval_anchor_hierarchy_match():
    case = GoldenCase(
        case_id="t1",
        question="dummy",
        expected_sources=["RL"],
        expected_anchors=[ExpectedAnchor(source_id="RL", anchor="§1-1")],
    )

    chunks = [
        ContextChunk(text="...", metadata={"source_id": "RL", "anchor": "§1-1(1)[a]"}),
    ]

    res = evaluate_case_on_chunks(case, chunks)
    assert res.pass_all
    assert res.hit_sources == ["RL"]
    assert res.hit_anchors == [{"source_id": "RL", "anchor": "§1-1"}]


def test_golden_eval_p_anchor_hierarchy_match():
    case = GoldenCase(
        case_id="t2",
        question="dummy",
        expected_sources=["ISA-230"],
        expected_anchors=[ExpectedAnchor(source_id="ISA-230", anchor="P8")],
    )

    chunks = [
        ContextChunk(text="...", metadata={"source_id": "ISA-230", "anchor": "P8.1"}),
    ]

    res = evaluate_case_on_chunks(case, chunks)
    assert res.pass_all
