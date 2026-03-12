from rag_assistant.anchors import anchor_hierarchy, anchor_sort_key, extract_legal_anchor, normalize_anchor


def test_normalize_anchor_legal_ledd_and_bokstav():
    assert normalize_anchor("§ 1-1") == "§1-1"
    assert normalize_anchor("§1-1 (1)") == "§1-1(1)"
    assert normalize_anchor("§1-1(1)a") == "§1-1(1)[a]"
    assert normalize_anchor("§1-1(1)[A]") == "§1-1(1)[a]"


def test_anchor_sort_key_orders_legal_hierarchy():
    anchors = ["§1-1(2)", "§1-1", "§1-1(1)[b]", "§1-1(1)", "§1-1(1)[a]"]
    sorted_anchors = sorted(anchors, key=anchor_sort_key)
    assert sorted_anchors == ["§1-1", "§1-1(1)", "§1-1(1)[a]", "§1-1(1)[b]", "§1-1(2)"]


def test_extract_legal_anchor_from_question_variants():
    assert extract_legal_anchor("Hva sier § 1-1?") == "§1-1"
    assert extract_legal_anchor("Hva sier §1-1 første ledd?") == "§1-1(1)"
    assert extract_legal_anchor("Se § 1-1 (2) bokstav a") == "§1-1(2)[a]"


def test_anchor_hierarchy_legal_and_standard():
    assert anchor_hierarchy("§1-1(1)[a]") == ["§1-1(1)[a]", "§1-1(1)", "§1-1"]
    assert anchor_hierarchy("§ 1-1 (1)") == ["§1-1(1)", "§1-1"]
    assert anchor_hierarchy("§1-1[b]") == ["§1-1[b]", "§1-1"]
    assert anchor_hierarchy("P1.2") == ["P1.2", "P1"]
    assert anchor_hierarchy("A3") == ["A3"]
