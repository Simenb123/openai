from types import SimpleNamespace

import rag_assistant.qa_cli as qa_cli


def test_cli_requires_question():
    assert qa_cli.main([]) == 2


def test_cli_no_llm(monkeypatch):
    # Patch collection + make_context så vi ikke trenger chroma/openai i test
    class FakeCollection:
        pass

    def fake_get_or_create_collection(*args, **kwargs):
        return FakeCollection()

    def fake_make_context(question, collection, **kwargs):
        chunk = SimpleNamespace(metadata={"source_id": "ISA-230", "anchor": "§1"})
        return "CTX", [chunk]

    monkeypatch.setattr(qa_cli, "get_or_create_collection", fake_get_or_create_collection)
    monkeypatch.setattr(qa_cli, "make_context", fake_make_context)

    rc = qa_cli.main(["--no-llm", "Hei"])
    assert rc == 0
