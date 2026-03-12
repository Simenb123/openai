from __future__ import annotations

from rag_assistant.kildebibliotek import Library, Relation, Source
from rag_assistant.pilot_isa230 import (
    build_default_scope,
    choose_pilot_source_ids,
    missing_source_ids,
    subset_library_to_sources,
)


def _lib(ids: list[str]) -> Library:
    sources = [Source(id=i, title=i, doc_type="OTHER", files=[]) for i in ids]
    rels = [
        Relation(from_id="ISA-230", to_id="RL", relation_type="RELATES_TO"),
        Relation(from_id="RL", to_id="RF", relation_type="IMPLEMENTS"),
        Relation(from_id="X", to_id="Y", relation_type="RELATES_TO"),
    ]
    return Library(version=1, sources=sources, relations=rels)


def test_missing_source_ids():
    lib = _lib(["RL"])
    assert missing_source_ids(lib, ["ISA-230", "RL"]) == ["ISA-230"]


def test_choose_pilot_source_ids_includes_optional_when_present():
    lib = _lib(["ISA-230", "RL", "RF"])
    ids = choose_pilot_source_ids(lib, include_optional=True)
    assert ids == ["ISA-230", "RL", "RF"]


def test_choose_pilot_source_ids_excludes_optional_when_flag_false():
    lib = _lib(["ISA-230", "RL", "RF"])
    ids = choose_pilot_source_ids(lib, include_optional=False)
    assert ids == ["ISA-230"]


def test_subset_library_to_sources_filters_relations_to_scope():
    lib = _lib(["ISA-230", "RL", "RF", "X", "Y"])
    sub = subset_library_to_sources(lib, ["ISA-230", "RL", "RF"])
    assert [s.id for s in sub.sources] == ["ISA-230", "RF", "RL"]
    # X->Y skal ikke følge med
    keys = [r.key() for r in sub.relations]
    assert any(k.startswith("ISA-230|") for k in keys)
    assert any(k.startswith("RL|") for k in keys)
    assert not any(k.startswith("X|") for k in keys)


def test_build_default_scope_reports_missing_required():
    lib = _lib(["RL", "RF"])
    scope = build_default_scope(lib)
    assert scope.missing_required == ["ISA-230"]
