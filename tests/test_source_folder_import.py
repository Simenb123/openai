from __future__ import annotations

import json
from pathlib import Path

from rag_assistant.kildebibliotek import Library
from rag_assistant.source_folder_import import import_sources_into_library


def test_import_sources_from_standard_folder(tmp_path: Path) -> None:
    # kilder/
    #   RL/
    #     source.json
    #     revisorloven.txt
    root = tmp_path / "kilder"
    rl = root / "RL"
    rl.mkdir(parents=True)
    (rl / "revisorloven.txt").write_text("§ 1-1 Virkeområde", encoding="utf-8")
    (rl / "source.json").write_text(
        json.dumps(
            {"id": "RL", "title": "Revisorloven", "doc_type": "LOV", "tags": ["lov"], "metadata": {"origin": "x"}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    lib = Library()
    res = import_sources_into_library(lib, root, base_dir=tmp_path)
    assert res.sources_added_or_updated == 1
    assert lib.get_source("RL") is not None
    src = lib.get_source("RL")
    assert src.title == "Revisorloven"
    assert src.doc_type == "LOV"
    assert src.tags == ["lov"]
    assert len(src.files) == 1
    # filsti lagres relativt
    assert src.files[0].startswith("kilder/RL/")


def test_import_creates_source_per_file_when_files_in_root(tmp_path: Path) -> None:
    root = tmp_path / "kilder"
    root.mkdir()
    (root / "isa230.txt").write_text("8. Krav", encoding="utf-8")
    (root / "revisorloven").write_text("§ 1-1", encoding="utf-8")  # ingen endelse -> støttet

    lib = Library()
    res = import_sources_into_library(lib, root, base_dir=tmp_path)
    assert res.sources_added_or_updated == 2
    assert lib.get_source("isa230") is not None
    assert lib.get_source("revisorloven") is not None


def test_import_skips_unsupported_files(tmp_path: Path) -> None:
    root = tmp_path / "kilder"
    root.mkdir()
    (root / "bad.bin").write_bytes(b"\x00\x01\x02")

    lib = Library()
    res = import_sources_into_library(lib, root, base_dir=tmp_path)
    assert res.sources_added_or_updated == 0
    assert res.warnings
