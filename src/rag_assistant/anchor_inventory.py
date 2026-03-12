from __future__ import annotations

"""rag_assistant.anchor_inventory

Dette modulen vedlikeholder en enkel "anker-inventory" per kilde (source_id).

Hvorfor?
  - For paragraf/punkt-relasjoner vil vi gi brukeren en liste over faktiske ankere
    som finnes i teksten (etter ingest/indeksering).
  - GUI kan da tilby autocomplete/dropdown når man lager relasjoner,
    slik at man unngår skrivefeil.

Format (JSON):
{
  "version": 1,
  "generated_at": "2026-02-22T12:34:56Z",
  "sources": {
    "RL": {
      "title": "Revisorloven",
      "doc_type": "LOV",
      "anchors": ["§1", "§1-1", "§1-1(1)", "§1-1(1)[a]", ...],
      "anchor_count": 123
    }
  }
}

Merk:
- Normalisering og sortering av ankere skjer via `rag_assistant.anchors`.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

from .anchors import anchor_sort_key, normalize_anchor


INVENTORY_VERSION = 1


def inventory_path_for_library(library_path: str | Path) -> Path:
    """Standard path for anker-inventory gitt en library json."""
    p = Path(library_path)
    # kildebibliotek.json -> kildebibliotek.anchors.json
    if p.suffix.lower() == ".json":
        return p.with_suffix(".anchors.json")
    return p.with_name(p.name + ".anchors.json")


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_anchor_inventory(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"version": INVENTORY_VERSION, "generated_at": None, "sources": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"version": INVENTORY_VERSION, "generated_at": None, "sources": {}}
    if "sources" not in data or not isinstance(data.get("sources"), dict):
        data["sources"] = {}
    data.setdefault("version", INVENTORY_VERSION)
    data.setdefault("generated_at", None)
    return data


def save_anchor_inventory(inventory: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(inventory, ensure_ascii=False, indent=2), encoding="utf-8")


def compute_anchor_inventory_from_items(items: Iterable[Any]) -> Dict[str, Dict[str, Any]]:
    """Bygger mapping: source_id -> {title, doc_type, anchors, anchor_count}.

    items forventes å ha attributter:
      - item.metadata (dict)
    """
    anchors_by_source: Dict[str, set[str]] = {}
    info_by_source: Dict[str, Dict[str, Any]] = {}

    for it in items:
        meta = getattr(it, "metadata", None) or {}
        sid = str(meta.get("source_id") or "").strip()
        if not sid:
            continue

        title = str(meta.get("source_title") or meta.get("title") or sid).strip() or sid
        doc_type = str(meta.get("doc_type") or "OTHER").strip() or "OTHER"
        info_by_source.setdefault(sid, {"title": title, "doc_type": doc_type})

        a = meta.get("anchor")
        if a is None:
            continue
        norm = normalize_anchor(str(a))
        if not norm:
            continue
        anchors_by_source.setdefault(sid, set()).add(norm)

    out: Dict[str, Dict[str, Any]] = {}

    # Kilder med anchors
    for sid, anchors in anchors_by_source.items():
        info = info_by_source.get(sid, {"title": sid, "doc_type": "OTHER"})
        anchors_sorted = sorted(anchors, key=anchor_sort_key)
        out[sid] = {
            "title": info.get("title") or sid,
            "doc_type": info.get("doc_type") or "OTHER",
            "anchors": anchors_sorted,
            "anchor_count": len(anchors_sorted),
        }

    # Kilder uten anchors: vi tar de også med (tom liste), for GUI.
    for sid, info in info_by_source.items():
        if sid in out:
            continue
        out[sid] = {
            "title": info.get("title") or sid,
            "doc_type": info.get("doc_type") or "OTHER",
            "anchors": [],
            "anchor_count": 0,
        }

    return out


def update_anchor_inventory_file(
    path: str | Path,
    items: Iterable[Any],
    *,
    replace_source_ids: Optional[Sequence[str]] = None,
    prune_to_source_ids: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Oppdaterer anker-inventory med nye data.

    - replace_source_ids: hvis angitt, begrens oppdatering til disse source_id-ene.
      (nyttig ved "Indekser valgt")
    - prune_to_source_ids: hvis angitt, fjern alle andre source_id-er fra inventory.
      (nyttig ved "Indekser alle" fra et library)
    """
    p = Path(path)
    inv = load_anchor_inventory(p)
    sources: Dict[str, Any] = inv.get("sources") or {}

    computed = compute_anchor_inventory_from_items(items)
    if replace_source_ids is not None:
        allowed = {str(x).strip() for x in replace_source_ids if str(x).strip()}
        computed = {sid: data for sid, data in computed.items() if sid in allowed}

    for sid, data in computed.items():
        sources[sid] = data

    if prune_to_source_ids is not None:
        keep = {str(x).strip() for x in prune_to_source_ids if str(x).strip()}
        for sid in list(sources.keys()):
            if sid not in keep:
                sources.pop(sid, None)

    inv["version"] = INVENTORY_VERSION
    inv["generated_at"] = _now_iso_z()
    inv["sources"] = sources
    save_anchor_inventory(inv, p)
    return inv
