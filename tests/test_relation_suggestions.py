from __future__ import annotations

from rag_assistant.relation_suggestions import (
    all_relation_type_keys,
    direction_hint,
    relation_type_description,
    relation_type_label,
    suggest_relation_types,
)


def test_all_relation_type_keys_is_non_empty_and_contains_core():
    keys = all_relation_type_keys()
    assert "RELATES_TO" in keys
    assert "REFERS_TO" in keys
    assert "CLARIFIES" in keys


def test_relation_type_label_and_description_exist_for_known_type():
    assert relation_type_label("AUTHORIZED_BY")
    assert "hjemmel" in relation_type_description("AUTHORIZED_BY").lower()


def test_suggest_relation_types_regulation_to_law():
    s = suggest_relation_types("FORSKRIFT", "LOV")
    # mest typisk først
    assert s[0] == "AUTHORIZED_BY"
    assert "RELATES_TO" in s


def test_suggest_relation_types_isa_to_law():
    s = suggest_relation_types("ISA", "LOV")
    assert s[0] in {"APPLIES_TO", "REFERS_TO"}
    assert "RELATES_TO" in s


def test_direction_hint_when_unusual_direction():
    hint = direction_hint("LOV", "FORSKRIFT")
    assert hint is not None
    assert "Bytt" in hint
