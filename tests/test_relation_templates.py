from __future__ import annotations

from rag_assistant.relation_templates import describe_applicable_template, templates_for_pair


def test_templates_for_pair_forward():
    apps = templates_for_pair("FORSKRIFT", "LOV")
    assert apps, "Forventet minst én mal for FORSKRIFT->LOV"
    keys = [a.template.key for a in apps]
    assert "FORSKRIFT_HJEMLET_I_LOV" in keys
    # forward
    app = [a for a in apps if a.template.key == "FORSKRIFT_HJEMLET_I_LOV"][0]
    assert app.direction == "forward"


def test_templates_for_pair_reverse_marks_swap():
    apps = templates_for_pair("LOV", "FORSKRIFT")
    keys = [a.template.key for a in apps]
    assert "FORSKRIFT_HJEMLET_I_LOV" in keys
    app = [a for a in apps if a.template.key == "FORSKRIFT_HJEMLET_I_LOV"][0]
    assert app.direction == "reverse"
    desc = describe_applicable_template(app)
    assert "anbefaler å bytte" in desc.lower()
