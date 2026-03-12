from pathlib import Path

from rag_assistant.kildebibliotek import Library, Relation, Source, load_library, save_library


def test_relation_key_includes_anchors():
    r = Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§ 1-1", to_anchor="§1-1")
    assert r.key() == "A|§1-1|RELATES_TO|B|§1-1"


def test_relation_key_keeps_legal_ledd_parenthesis_and_bokstav():
    r = Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§ 1-1 (1)", to_anchor="§1-1(1)a")
    assert r.from_anchor == "§1-1(1)"
    assert r.to_anchor == "§1-1(1)[a]"
    assert r.key() == "A|§1-1(1)|RELATES_TO|B|§1-1(1)[a]"


def test_library_related_targets_anchor_filtering():
    lib = Library()
    lib.sources = [Source(id="A", title="A"), Source(id="B", title="B")]
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§1", to_anchor="§1-1"))
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor=None, to_anchor=None))

    # Med anchor: relasjon med from_anchor=§1 skal matches, samt dokumentnivå-relasjon (from_anchor None)
    targets = lib.related_targets("A", anchor="§ 1", direction="out")
    assert ("B", "§1-1", "RELATES_TO", None) in targets
    assert ("B", None, "RELATES_TO", None) in targets

    # Med anchor som ikke matcher: kun dokumentnivå-relasjon skal gjenstå
    targets2 = lib.related_targets("A", anchor="§9", direction="out")
    assert targets2 == [("B", None, "RELATES_TO", None)]


def test_library_related_targets_supports_hierarchical_anchor_fallback():
    lib = Library()
    lib.sources = [Source(id="A", title="A"), Source(id="B", title="B")]

    # Relasjon definert på paragrafnivå
    lib.upsert_relation(Relation(from_id="A", to_id="B", relation_type="RELATES_TO", from_anchor="§1-1"))

    # Spørsmål på bokstavnivå skal likevel matche (hierarkisk fallback)
    targets = lib.related_targets("A", anchor="§1-1(1)[a]", direction="out")
    assert ("B", None, "RELATES_TO", None) in targets


def test_library_related_targets_supports_hierarchical_anchor_fallback_for_standards():
    lib = Library()
    lib.sources = [Source(id="S", title="S"), Source(id="T", title="T")]

    # Relasjon definert på P1
    lib.upsert_relation(Relation(from_id="S", to_id="T", relation_type="REFERS_TO", from_anchor="P1"))

    # Spørsmål på P1.2 skal matche P1-relasjonen
    targets = lib.related_targets("S", anchor="P1.2", direction="out")
    assert ("T", None, "REFERS_TO", None) in targets


def test_load_save_roundtrip(tmp_path: Path):
    lib = Library()
    lib.upsert_source(Source(id="ISA-230", title="ISA 230", doc_type="ISA", files=["kilder/isa230.txt"]))
    lib.upsert_relation(Relation(from_id="ISA-230", to_id="RL", relation_type="REFERS_TO", from_anchor="§1", to_anchor="§1"))

    p = tmp_path / "kildebibliotek.json"
    save_library(lib, p)
    loaded = load_library(p)

    assert loaded.get_source("ISA-230") is not None
    assert len(loaded.relations) == 1
    assert loaded.relations[0].from_anchor == "§1"
