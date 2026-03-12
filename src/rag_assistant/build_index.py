from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .file_ingest import ingest_files
from .kildebibliotek import Library, load_library
from .rag_index import delete_all_documents, delete_where, get_or_create_collection, upsert_documents
from .settings_profiles import Settings, apply_env, load_settings
from .anchor_inventory import inventory_path_for_library, update_anchor_inventory_file


def _sha1(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _make_chunk_id(source_path: str, idx: int) -> str:
    # Stabil-ish: basert på path + indeks
    h = _sha1(source_path)[:10]
    return f"{h}_{idx:06d}"


def _make_chunk_id_with_source_id(source_id: str, idx: int, *, file_hash: str) -> str:
    sid = (source_id or "").strip() or "SRC"
    return f"{sid}_{idx:06d}_{file_hash}"


@dataclass
class BuildItem:
    id: str
    text: str
    metadata: Dict[str, Any]


def build_items_from_path(
    input_path: str | Path,
    *,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> List[BuildItem]:
    docs = ingest_files(input_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    items: List[BuildItem] = []
    for d in docs:
        meta = dict(d.get("metadata") or {})
        source_path = str(meta.get("source_path") or input_path)
        idx = int(meta.get("chunk_index") or 0)
        doc_id = _make_chunk_id(source_path, idx)
        items.append(BuildItem(id=doc_id, text=str(d.get("text") or ""), metadata=meta))
    return items


def build_items_from_library(
    library: Library,
    *,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> List[BuildItem]:
    items: List[BuildItem] = []
    for src in library.sources:
        base_meta = {
            "source_id": src.id,
            "source_title": src.title,
            "doc_type": src.doc_type,
            "tags": ",".join(src.tags) if src.tags else "",
        }
        base_meta.update(src.metadata or {})

        for file_path in src.files:
            docs = ingest_files(
                file_path,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                base_metadata=base_meta,
            )
            file_hash = _sha1(str(Path(file_path).as_posix()))[:6]
            for d in docs:
                meta = dict(d.get("metadata") or {})
                idx = int(meta.get("chunk_index") or 0)
                doc_id = _make_chunk_id_with_source_id(src.id, idx, file_hash=file_hash)
                items.append(BuildItem(id=doc_id, text=str(d.get("text") or ""), metadata=meta))
    return items


def build_index_from_path(
    input_path: str | Path,
    *,
    settings: Optional[Settings] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    wipe_collection: bool = False,
) -> int:
    cfg = settings or load_settings()
    apply_env(cfg)
    col = get_or_create_collection(
        db_path=cfg.db_path, collection_name=cfg.collection, embedding_model=cfg.embedding_model
    )

    # A1: Unngå "stale" chunks ved reindeksering.
    # For path-baserte bygg kan vi kun tilby eksplisitt wipe av hele collection.
    if wipe_collection:
        delete_all_documents(col)
    items = build_items_from_path(input_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    upsert_documents(col, [i.text for i in items], [i.metadata for i in items], [i.id for i in items])
    return len(items)


def build_index_from_library(
    library: Library,
    *,
    settings: Optional[Settings] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    purge_existing: bool = True,
    wipe_collection: bool = False,
    anchor_inventory_path: Optional[str | Path] = None,
    prune_anchor_inventory: bool = False,
) -> int:
    cfg = settings or load_settings()
    apply_env(cfg)
    col = get_or_create_collection(
        db_path=cfg.db_path, collection_name=cfg.collection, embedding_model=cfg.embedding_model
    )

    # A1: Unngå "stale" chunks ved reindeksering.
    # - wipe_collection=True: sletter alt (passer "Indekser alle")
    # - purge_existing=True: sletter kun for source_id-ene vi skal indeksere (passer "Indekser valgt")
    if wipe_collection:
        delete_all_documents(col)
    elif purge_existing:
        for src in library.sources:
            if src.id:
                delete_where(col, {"source_id": src.id})
    items = build_items_from_library(library, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    upsert_documents(col, [i.text for i in items], [i.metadata for i in items], [i.id for i in items])

    # C1: Oppdater anker-inventory etter indeksering.
    # - Ved "Indekser valgt": skriv kun for den/de kildene vi bygde her, men ikke prune.
    # - Ved "Indekser alle": prune=true slik at inventory reflekterer biblioteket.
    if anchor_inventory_path:
        source_ids = [s.id for s in library.sources if s.id]
        update_anchor_inventory_file(
            anchor_inventory_path,
            items,
            replace_source_ids=source_ids,
            prune_to_source_ids=source_ids if prune_anchor_inventory else None,
        )
    return len(items)


def build_index_from_library_file(
    library_path: str | Path,
    *,
    settings: Optional[Settings] = None,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    purge_existing: bool = True,
    wipe_collection: bool = False,
    anchor_inventory_path: Optional[str | Path] = None,
) -> int:
    lib = load_library(library_path)

    # Default: anker-inventory ved siden av kildebiblioteket (kildebibliotek.anchors.json)
    inv_path = Path(anchor_inventory_path) if anchor_inventory_path else inventory_path_for_library(library_path)

    return build_index_from_library(
        lib,
        settings=settings,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        purge_existing=purge_existing,
        wipe_collection=wipe_collection,
        anchor_inventory_path=inv_path,
        prune_anchor_inventory=True,
    )
