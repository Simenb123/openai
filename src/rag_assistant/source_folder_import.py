from __future__ import annotations

"""rag_assistant.source_folder_import

Standardisert import av kilder fra en mappe.

Mål:
- Gjøre det lett å legge til kilder på et konsekvent format uten å klikke alt inn i GUI.
- Fungere både via GUI og CLI.
- Ikke være "magisk": importen er best-effort og gir advarsler for ting som hoppes over.

Standardformat (anbefalt):

kilder/
  RL/
    source.json
    revisorloven.txt
  RF/
    source.json
    revisorforskriften.txt
  ISA-230/
    source.json
    isa230.txt

Der `source.json` kan se slik ut:

{
  "id": "RL",
  "title": "Revisorloven",
  "doc_type": "LOV",
  "tags": ["lov"],
  "metadata": {
    "origin": "Lovdata",
    "language": "no"
  }
}

Regler:
- Hvis `source.json` mangler:
  - id = mappenavn
  - title = mappenavn
  - doc_type = OTHER
- Filer i kildemappen:
  - inkludér .txt/.pdf/.docx og filer uten endelse (behandles som txt)
  - ignorer source.json og skjulte filer
- Hvis du velger en mappe som inneholder filer direkte, opprettes én Source per fil.
  (id = filnavn uten endelse, title = samme)

Importen oppdaterer `Library` ved å upsert'e Source.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .kildebibliotek import Library, Source


SUPPORTED_EXTS = {"txt", "pdf", "docx", ""}  # "" = ingen endelse (txt)


@dataclass(frozen=True)
class ImportResult:
    sources_added_or_updated: int
    warnings: List[str]


def _is_hidden(p: Path) -> bool:
    name = p.name
    return name.startswith(".") or name.lower() in {"thumbs.db", "desktop.ini"}


def _try_make_relative(path: Path, base_dir: Path) -> str:
    try:
        rel = path.resolve().relative_to(base_dir.resolve())
        return rel.as_posix()
    except Exception:
        return str(path.resolve())


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _collect_files(folder: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        if _is_hidden(p):
            continue
        if p.name.lower() == "source.json":
            continue
        ext = p.suffix.lower().lstrip(".")
        if ext not in SUPPORTED_EXTS:
            continue
        files.append(p)
    return files


def _source_from_folder(folder: Path, *, base_dir: Path) -> Tuple[Optional[Source], List[str]]:
    warnings: List[str] = []
    meta_path = folder / "source.json"
    meta = _load_json(meta_path) if meta_path.exists() else {}

    sid = str(meta.get("id") or folder.name).strip()
    if not sid:
        return None, [f"Hopper over kilde (tom id): {folder}"]

    title = str(meta.get("title") or folder.name).strip() or sid
    doc_type = str(meta.get("doc_type") or "OTHER").strip() or "OTHER"
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()]

    md = meta.get("metadata") or {}
    if not isinstance(md, dict):
        md = {}

    files = _collect_files(folder)
    if not files:
        warnings.append(f"Ingen støttede filer funnet i {folder}")
        return None, warnings

    file_paths = [_try_make_relative(f, base_dir) for f in files]
    src = Source(id=sid, title=title, doc_type=doc_type, files=file_paths, tags=tags, metadata=md)
    return src, warnings


def _source_from_file(file_path: Path, *, base_dir: Path) -> Tuple[Optional[Source], List[str]]:
    warnings: List[str] = []
    if not file_path.is_file():
        return None, [f"Ikke en fil: {file_path}"]
    if _is_hidden(file_path):
        return None, []
    ext = file_path.suffix.lower().lstrip(".")
    if ext not in SUPPORTED_EXTS:
        return None, [f"Ikke støttet filtype: {file_path.name}"]
    sid = file_path.stem.strip() or file_path.name
    fp = _try_make_relative(file_path, base_dir)
    src = Source(id=sid, title=sid, doc_type="OTHER", files=[fp], tags=[], metadata={})
    return src, warnings


def import_sources_into_library(
    library: Library,
    source_root: str | Path,
    *,
    base_dir: Optional[str | Path] = None,
) -> ImportResult:
    """Importer kilder fra `source_root` inn i `library`.

    - base_dir brukes for å lagre relative filstier (typisk prosjektroten).
    - Oppdaterer library in-place via upsert_source.

    Returnerer ImportResult med antall sources og warnings.
    """
    root = Path(source_root)
    if not root.exists() or not root.is_dir():
        return ImportResult(0, [f"Finner ikke mappe: {root}"])

    base = Path(base_dir) if base_dir else Path.cwd()

    warnings: List[str] = []
    added = 0

    # Hvis root selv inneholder source.json => behandle root som én kilde
    if (root / "source.json").exists():
        src, w = _source_from_folder(root, base_dir=base)
        warnings.extend(w)
        if src:
            library.upsert_source(src)
            added += 1
        return ImportResult(added, warnings)

    # Ellers: subfolder = source, filer i root = hver sin source
    for p in sorted(root.iterdir()):
        if _is_hidden(p):
            continue
        if p.is_dir():
            src, w = _source_from_folder(p, base_dir=base)
            warnings.extend(w)
            if src:
                library.upsert_source(src)
                added += 1
        elif p.is_file():
            src, w = _source_from_file(p, base_dir=base)
            warnings.extend(w)
            if src:
                library.upsert_source(src)
                added += 1

    return ImportResult(added, warnings)
