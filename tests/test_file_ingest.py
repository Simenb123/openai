from pathlib import Path

from rag_assistant.file_ingest import chunk_text, ingest_files


def test_chunk_text_validates_overlap():
    try:
        chunk_text("abc", chunk_size=10, chunk_overlap=10)
        assert False, "should raise"
    except ValueError:
        pass


def test_ingest_extensionless_file_treated_as_txt(tmp_path: Path):
    f = tmp_path / "revisorloven"  # ingen endelse
    f.write_text("§ 2 Formål\nDette er en test.", encoding="utf-8")

    docs = ingest_files(f, chunk_size=200, chunk_overlap=0)
    assert len(docs) >= 1
    meta = docs[0]["metadata"]
    assert meta.get("file_ext") == "txt"
    assert meta.get("anchor") == "§2"


def test_ingest_directory_skips_unsupported(tmp_path: Path):
    ok = tmp_path / "ok.txt"
    ok.write_text("§ 1 Hei", encoding="utf-8")
    bad = tmp_path / "bad.bin"
    bad.write_bytes(b"\x00\x01\x02")

    docs = ingest_files(tmp_path, chunk_size=200, chunk_overlap=0)
    assert any("Hei" in d["text"] for d in docs)


def test_ingest_isa_paragraph_and_application_anchors(tmp_path: Path):
    f = tmp_path / "isa230.txt"
    f.write_text(
        """Innledning før første punkt

1. Formål
Dette er formålet.

8. Krav til revisjonsdokumentasjon
Kravtekst.

A1 Veiledning
Mer tekst.

A2 Mer veiledning
Enda mer tekst.
""",
        encoding="utf-8",
    )

    docs = ingest_files(f, chunk_size=10_000, chunk_overlap=0)
    anchors = {d["metadata"].get("anchor") for d in docs}
    assert "P1" in anchors
    assert "P8" in anchors
    assert "A1" in anchors
    assert "A2" in anchors


def test_ingest_legal_ledd_and_bokstav_anchors(tmp_path: Path):
    f = tmp_path / "lov.txt"
    f.write_text(
        """§ 1-1 Virkeområde
(1) Første ledd.
(2) Andre ledd.

§ 2-1 Krav
(1) Ledd med bokstaver:
  a) Første bokstav.
  b) Andre bokstav.
""",
        encoding="utf-8",
    )

    docs = ingest_files(f, chunk_size=50_000, chunk_overlap=0)
    anchors = {d["metadata"].get("anchor") for d in docs}

    assert "§1-1" in anchors
    assert "§1-1(1)" in anchors
    assert "§1-1(2)" in anchors

    assert "§2-1" in anchors
    assert "§2-1(1)" in anchors
    assert "§2-1(1)[a]" in anchors
    assert "§2-1(1)[b]" in anchors
