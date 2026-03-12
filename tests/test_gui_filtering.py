from __future__ import annotations

from rag_assistant.gui.filtering import filter_relations, filter_sources, tokenize_query
from rag_assistant.kildebibliotek import Relation, Source


def test_tokenize_query_splits_whitespace_and_lowercases():
    assert tokenize_query("  ISA  230  ") == ["isa", "230"]


def test_filter_sources_matches_id_title_type_and_tags():
    sources = [
        Source(id="ISA-230", title="ISA 230 Revisjonsdokumentasjon", doc_type="ISA", tags=["isa", "dokumentasjon"]),
        Source(id="RL", title="Revisorloven", doc_type="LOV", tags=["lov"]),
    ]

    # match on id
    out = filter_sources(sources, "RL")
    assert [s.id for s in out] == ["RL"]

    # match on title token
    out = filter_sources(sources, "revisjons")
    assert [s.id for s in out] == ["ISA-230"]

    # match on doc_type
    out = filter_sources(sources, "lov")
    assert [s.id for s in out] == ["RL"]

    # AND semantics
    out = filter_sources(sources, "isa 230")
    assert [s.id for s in out] == ["ISA-230"]


def test_filter_relations_matches_anchors_type_and_note():
    rels = [
        Relation(from_id="RL", to_id="RF", relation_type="IMPLEMENTS", from_anchor="§1", to_anchor="§1-1"),
        Relation(
            from_id="ISA-230",
            to_id="RL",
            relation_type="RELATES_TO",
            from_anchor="P8",
            to_anchor="§1-1",
            note="kobler dokumentasjon til lovkrav",
        ),
    ]

    out = filter_relations(rels, "P8")
    assert len(out) == 1
    assert out[0].from_id == "ISA-230"

    out = filter_relations(rels, "implements")
    assert len(out) == 1
    assert out[0].relation_type == "IMPLEMENTS"

    out = filter_relations(rels, "dokumentasjon lovkrav")
    assert len(out) == 1
    assert out[0].from_id == "ISA-230"
