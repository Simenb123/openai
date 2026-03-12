from __future__ import annotations

from pathlib import Path

from rag_assistant.anchor_texts import build_anchor_text_map
from rag_assistant.kildebibliotek import Library, Source


def test_build_anchor_text_map_includes_subanchors(tmp_path: Path):
    # Lovtekst med paragraf + ledd + bokstav
    text = """§ 1-1 Formål
(1) Dette er første ledd.
a) Bokstav a.
b) Bokstav b.

§ 2-3 Annet
Dette er paragraf 2-3.
"""

    (tmp_path / "rl.txt").write_text(text, encoding="utf-8")

    lib = Library(
        sources=[
            Source(id="RL", title="Revisorloven", doc_type="LOV", files=["rl.txt"]),
        ],
        relations=[],
    )

    amap = build_anchor_text_map(lib, "RL", base_dir=tmp_path)
    # Paragraf
    assert "§1-1" in amap
    # Ledd
    assert "§1-1(1)" in amap
    # Bokstav
    assert "§1-1(1)[a]" in amap
    assert "§1-1(1)[b]" in amap
    # Andre paragraf
    assert "§2-3" in amap
