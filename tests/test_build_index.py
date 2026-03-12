from pathlib import Path

from rag_assistant.build_index import build_items_from_library
from rag_assistant.kildebibliotek import Library, Source


def test_build_items_from_library_includes_source_metadata(tmp_path: Path):
    f = tmp_path / "revisorloven"
    f.write_text("§ 1-1 Virkeområde\nDette er en testtekst.", encoding="utf-8")

    lib = Library()
    lib.upsert_source(
        Source(
            id="RL",
            title="Revisorloven",
            doc_type="LOV",
            files=[str(f)],
            tags=["lov"],
            metadata={"language": "no"},
        )
    )

    items = build_items_from_library(lib, chunk_size=300, chunk_overlap=0)
    assert len(items) >= 1
    it = items[0]
    assert it.metadata["source_id"] == "RL"
    assert it.metadata["doc_type"] == "LOV"
    assert it.metadata["language"] == "no"
    assert it.metadata.get("anchor") == "§1-1"
    assert it.id.startswith("RL_")
