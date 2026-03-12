from pathlib import Path

import pytest

from rag_assistant.document_ingestor import DocumentIngestor


def test_parse_txt_and_extensionless(tmp_path: Path):
    txt = tmp_path / "a.txt"
    txt.write_text("Hei æøå", encoding="utf-8")
    extless = tmp_path / "b"
    extless.write_text("§ 2 Formål", encoding="utf-8")

    ing = DocumentIngestor()

    d1 = ing.parse_file(txt)
    assert "Hei" in d1.text
    assert d1.metadata["file_ext"] == "txt"

    d2 = ing.parse_file(extless)
    assert "Formål" in d2.text
    assert d2.metadata["file_ext"] == "txt"  # extensionless -> txt


def test_parse_unsupported_extension_raises(tmp_path: Path):
    f = tmp_path / "x.bin"
    f.write_bytes(b"\x00\x01")
    ing = DocumentIngestor()
    with pytest.raises(ValueError):
        ing.parse_file(f)
