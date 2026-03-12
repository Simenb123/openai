from __future__ import annotations

from pathlib import Path

from rag_assistant.kildebibliotek import Library, Source
from rag_assistant.relation_proposals import propose_relations_for_pair


def test_propose_relations_for_pair_scans_anchors(tmp_path: Path):
    # Arrange: from-source (ISA) med et par P-ankere og referanser til lovparagrafer
    isa_text = (
        "8. Dette er punkt 8. Se § 1-1 (1) bokstav a.\n"
        "9. Dette er punkt 9. Se § 2-3.\n"
    )
    (tmp_path / "isa.txt").write_text(isa_text, encoding="utf-8")

    lib = Library(
        sources=[
            Source(id="ISA-230", title="ISA 230 Revisjonsdokumentasjon", doc_type="ISA", files=["isa.txt"]),
            Source(id="RL", title="Revisorloven", doc_type="LOV", files=[]),
        ],
        relations=[],
    )

    anchor_inventory = {
        "version": 1,
        "generated_at": "test",
        "sources": {
            "RL": {
                "title": "Revisorloven",
                "doc_type": "LOV",
                "anchors": ["§1-1(1)[a]", "§2-3"],
                "anchor_count": 2,
            }
        },
    }

    # Act
    res = propose_relations_for_pair(
        lib,
        from_source_id="ISA-230",
        to_source_id="RL",
        anchor_inventory=anchor_inventory,
        base_dir=tmp_path,
        include_unknown_anchors=True,
        fallback_doc_level=False,
    )

    # Assert
    assert not res.warnings
    assert res.proposals, "Forventet forslag"

    # Finn forslag med P8 -> §1-1(1)[a]
    found = [
        p
        for p in res.proposals
        if p.relation.from_anchor == "P8" and p.relation.to_anchor == "§1-1(1)[a]" and p.known_target_anchor
    ]
    assert found, "Mangler forventet forslag P8 -> §1-1(1)[a]"
