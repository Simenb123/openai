from __future__ import annotations

from pathlib import Path

import rag_assistant.qa_service as qa_service
from rag_assistant.rag_bridge import ContextChunk


class FakeCollection:
    def __init__(self):
        self.calls = []

    def query(self, *, query_texts, n_results, where=None):
        self.calls.append({"query_texts": query_texts, "n_results": n_results, "where": where})
        return {
            "documents": [["Dette er en kontekst."]],
            "metadatas": [[{"source_id": "ISA-230", "anchor": "P8"}]],
            "ids": [["x1"]],
        }


def test_format_sources_dedupes_same_source_anchor():
    chunks = [
        ContextChunk(text="a", metadata={"source_id": "ISA-230", "anchor": "P8"}),
        ContextChunk(text="b", metadata={"source_id": "ISA-230", "anchor": "P8"}),
        ContextChunk(text="c", metadata={"source_id": "RL", "anchor": "§1-1"}),
    ]
    s = qa_service.format_sources(chunks)
    assert s.count("ISA-230 P8") == 1
    assert "RL §1-1" in s


def test_retrieve_only_uses_make_context(monkeypatch, tmp_path: Path):
    fake_col = FakeCollection()

    class FakeSettings:
        db_path = "ragdb"
        collection = "revisjon"
        embedding_model = "text-embedding-3-small"
        chat_model = "gpt-4o-mini"
        base_url = None

    monkeypatch.setattr(qa_service, "load_settings", lambda: FakeSettings())
    monkeypatch.setattr(qa_service, "get_or_create_collection", lambda **kwargs: fake_col)

    def fake_make_context(question, collection, *, n_results, library_path=None, expand_relations=True):
        assert question == "Hva sier ISA 230 punkt 8?"
        assert collection is fake_col
        assert n_results == 7
        return (
            "CTX",
            [ContextChunk(text="Dette er en kontekst.", metadata={"source_id": "ISA-230", "anchor": "P8"}, chunk_id="x1")],
        )

    monkeypatch.setattr(qa_service, "make_context", fake_make_context)

    out = qa_service.retrieve_only(
        "Hva sier ISA 230 punkt 8?",
        settings=FakeSettings(),
        library_path=tmp_path / "kildebibliotek.json",
        n_results=7,
        expand_relations=True,
    )
    assert out.question.startswith("Hva sier ISA 230")
    assert out.context == "CTX"
    assert "ISA-230 P8" in out.sources_text


def test_run_golden_suite_calls_eval_and_saves(monkeypatch, tmp_path: Path):
    fake_col = FakeCollection()

    class FakeSettings:
        db_path = "ragdb"
        collection = "revisjon"
        embedding_model = "text-embedding-3-small"
        chat_model = "gpt-4o-mini"
        base_url = None

    monkeypatch.setattr(qa_service, "load_settings", lambda: FakeSettings())
    monkeypatch.setattr(qa_service, "get_or_create_collection", lambda **kwargs: fake_col)
    monkeypatch.setattr(qa_service, "load_golden_cases", lambda path: ["case1"])
    monkeypatch.setattr(
        qa_service,
        "run_golden_eval",
        lambda cases, *, collection, library_path=None, n_results=5, expand_relations=True: {
            "cases": 1,
            "passed": 1,
            "failed": 0,
            "results": [],
        },
    )

    saved = {}

    def fake_save(report, path):
        saved["report"] = report
        saved["path"] = Path(path)

    monkeypatch.setattr(qa_service, "save_report", fake_save)

    out = qa_service.run_golden_suite(
        golden_path=tmp_path / "golden.json",
        report_path=tmp_path / "report.json",
        settings=FakeSettings(),
        library_path=tmp_path / "kildebibliotek.json",
        n_results=3,
        expand_relations=False,
    )
    assert out.report["passed"] == 1
    assert saved["path"].name == "report.json"
