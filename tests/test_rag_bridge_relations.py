from pathlib import Path

from rag_assistant.kildebibliotek import Library, Relation, Source, save_library
from rag_assistant.rag_bridge import extract_anchor, make_context


class FakeCollection:
    def __init__(self):
        self.calls = []

    def query(self, *, query_texts, n_results, where=None):
        self.calls.append({"query_texts": query_texts, "n_results": n_results, "where": where})

        # Base query (where None)
        if where is None:
            return {
                "documents": [["Base doc"]],
                "metadatas": [[{"source_id": "A", "anchor": "§1-1"}]],
                "ids": [["base1"]],
            }

        # Expansion query for B
        if where.get("source_id") == "B":
            return {
                "documents": [["Relatert doc B"]],
                "metadatas": [[{"source_id": "B", "anchor": where.get("anchor") }]],
                "ids": [["b1"]],
            }

        return {"documents": [[]], "metadatas": [[]], "ids": [[]]}


def test_make_context_expands_when_anchor_present(tmp_path: Path):
    # library A §1-1 -> B (samme anchor)
    lib = Library()
    lib.sources = [Source(id="A", title="A"), Source(id="B", title="B")]
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§1-1"))

    lib_path = tmp_path / "kildebibliotek.json"
    save_library(lib, lib_path)

    col = FakeCollection()
    context, chunks = make_context("Hva sier A § 1-1?", col, library_path=lib_path, n_results=1)

    assert len(col.calls) >= 2
    # 2. kall skal være ekspansjon mot B
    assert col.calls[1]["where"]["source_id"] == "B"
    assert col.calls[1]["where"]["anchor"] == "§1-1"
    assert "Relatert doc B" in context


def test_make_context_expands_with_anchor_parent_fallback(tmp_path: Path):
    """D2: Hvis spørsmålet har mer spesifikk anchor enn relasjonen/indeksen støtter, skal vi likevel ekspandere."""

    class ParentOnlyCollection(FakeCollection):
        def query(self, *, query_texts, n_results, where=None):
            self.calls.append({"query_texts": query_texts, "n_results": n_results, "where": where})

            # Base query
            if where is None:
                return {
                    "documents": [["Base doc"]],
                    "metadatas": [[{"source_id": "A", "anchor": "§1-1(1)[a]"}]],
                    "ids": [["base1"]],
                }

            # Expansion: kun parent-anker finnes i mål-kilden
            if where.get("source_id") == "B":
                if where.get("anchor") == "§1-1":
                    return {
                        "documents": [["Relatert doc B (parent)"]],
                        "metadatas": [[{"source_id": "B", "anchor": "§1-1"}]],
                        "ids": [["b1"]],
                    }
                return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

            return {"documents": [[]], "metadatas": [[]], "ids": [[]]}

    # Relasjon definert på paragrafnivå
    lib = Library()
    lib.sources = [Source(id="A", title="A"), Source(id="B", title="B")]
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§1-1"))

    lib_path = tmp_path / "kildebibliotek.json"
    save_library(lib, lib_path)

    col = ParentOnlyCollection()
    context, chunks = make_context("Hva sier § 1-1 (1) bokstav a?", col, library_path=lib_path, n_results=1)

    # Vi forventer flere forsøk: §1-1(1)[a] -> §1-1(1) -> §1-1
    anchors_tried = [c["where"].get("anchor") for c in col.calls if c["where"] and c["where"].get("source_id") == "B"]
    assert "§1-1" in anchors_tried
    assert "Relatert doc B (parent)" in context


def test_make_context_does_not_expand_when_anchor_missing(tmp_path: Path):
    # library har relasjon, men vi skal ikke ekspandere hvis anchor ikke kan utledes
    lib = Library()
    lib.sources = [Source(id="A", title="A"), Source(id="B", title="B")]
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO"))

    lib_path = tmp_path / "kildebibliotek.json"
    save_library(lib, lib_path)

    class NoAnchorBase(FakeCollection):
        def query(self, *, query_texts, n_results, where=None):
            self.calls.append({"query_texts": query_texts, "n_results": n_results, "where": where})
            if where is None:
                return {
                    "documents": [["Base doc"]],
                    "metadatas": [[{"source_id": "A"}]],  # ingen anchor
                    "ids": [["base1"]],
                }
            return super().query(query_texts=query_texts, n_results=n_results, where=where)

    col = NoAnchorBase()
    context, chunks = make_context("Hva sier A om dette?", col, library_path=lib_path, n_results=1)
    assert len(col.calls) == 1  # kun base query


def test_extract_anchor_supports_pkt_abbrev():
    assert extract_anchor("ISA 230 pkt 8") == "P8"
    assert extract_anchor("punkt 12") == "P12"
    assert extract_anchor("A1") == "A1"


def test_extract_anchor_supports_legal_ledd_and_bokstav():
    assert extract_anchor("Revisorloven § 1-1 første ledd") == "§1-1(1)"
    assert extract_anchor("Se § 1-1 (2) bokstav a") == "§1-1(2)[a]"
    assert extract_anchor("§1-1 bokstav b") == "§1-1[b]"
