from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .anchors import anchor_hierarchy, normalize_anchor


def _norm_anchor(anchor: Optional[str]) -> Optional[str]:
    """Normaliserer relasjons-ankere.

    Vi bruker samme normalisering som resten av systemet (rag_assistant.anchors).
    """
    return normalize_anchor(anchor)


@dataclass
class Source:
    id: str
    title: str
    doc_type: str = "OTHER"
    files: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = self.id.strip()
        if not self.id:
            raise ValueError("Source.id kan ikke være tom")
        self.title = (self.title or "").strip() or self.id
        self.doc_type = (self.doc_type or "OTHER").strip() or "OTHER"
        self.files = [str(f) for f in (self.files or []) if str(f).strip()]
        self.tags = [t.strip() for t in (self.tags or []) if t.strip()]
        self.metadata = dict(self.metadata or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "doc_type": self.doc_type,
            "files": list(self.files),
            "tags": list(self.tags),
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Source":
        return Source(
            id=str(d.get("id") or ""),
            title=str(d.get("title") or ""),
            doc_type=str(d.get("doc_type") or "OTHER"),
            files=list(d.get("files") or []),
            tags=list(d.get("tags") or []),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class Relation:
    from_id: str
    to_id: str
    relation_type: str = "RELATES_TO"
    from_anchor: Optional[str] = None
    to_anchor: Optional[str] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        self.from_id = (self.from_id or "").strip()
        self.to_id = (self.to_id or "").strip()
        if not self.from_id or not self.to_id:
            raise ValueError("Relation må ha from_id og to_id")
        self.relation_type = (self.relation_type or "RELATES_TO").strip() or "RELATES_TO"
        self.from_anchor = _norm_anchor(self.from_anchor)
        self.to_anchor = _norm_anchor(self.to_anchor)
        if self.note is not None:
            self.note = self.note.strip() or None

    def key(self) -> str:
        # unik nøkkel, også når vi knytter ankere
        return f"{self.from_id}|{self.from_anchor or ''}|{self.relation_type}|{self.to_id}|{self.to_anchor or ''}"

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "relation_type": self.relation_type,
        }
        if self.from_anchor:
            d["from_anchor"] = self.from_anchor
        if self.to_anchor:
            d["to_anchor"] = self.to_anchor
        if self.note:
            d["note"] = self.note
        return d

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Relation":
        return Relation(
            from_id=str(d.get("from_id") or ""),
            to_id=str(d.get("to_id") or ""),
            relation_type=str(d.get("relation_type") or "RELATES_TO"),
            from_anchor=d.get("from_anchor") or None,
            to_anchor=d.get("to_anchor") or None,
            note=d.get("note") or None,
        )


@dataclass
class Library:
    version: int = 1
    sources: List[Source] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "sources": [s.to_dict() for s in self.sources],
            "relations": [r.to_dict() for r in self.relations],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Library":
        lib = Library(version=int(d.get("version") or 1))
        lib.sources = [Source.from_dict(x) for x in (d.get("sources") or [])]
        lib.relations = [Relation.from_dict(x) for x in (d.get("relations") or [])]
        return lib

    # ---- Sources ----

    def get_source(self, source_id: str) -> Optional[Source]:
        sid = (source_id or "").strip()
        for s in self.sources:
            if s.id == sid:
                return s
        return None

    def upsert_source(self, src: Source) -> None:
        existing = self.get_source(src.id)
        if existing is None:
            self.sources.append(src)
            return
        existing.title = src.title
        existing.doc_type = src.doc_type
        existing.files = list(src.files)
        existing.tags = list(src.tags)
        existing.metadata = dict(src.metadata)

    def remove_source(self, source_id: str, *, remove_relations: bool = True) -> None:
        sid = (source_id or "").strip()
        self.sources = [s for s in self.sources if s.id != sid]
        if remove_relations:
            self.relations = [r for r in self.relations if r.from_id != sid and r.to_id != sid]

    # ---- Relations ----

    def upsert_relation(self, rel: Relation) -> None:
        key = rel.key()
        self.relations = [r for r in self.relations if r.key() != key]
        self.relations.append(rel)

    def remove_relation(self, rel: Relation) -> None:
        key = rel.key()
        self.relations = [r for r in self.relations if r.key() != key]

    def related_targets(
        self, source_id: str, *, anchor: Optional[str] = None, direction: str = "both"
    ) -> List[Tuple[str, Optional[str], str, Optional[str]]]:
        """Hent relaterte dokumenter (og evt. ankere).

        Returnerer liste av (target_id, target_anchor, relation_type, note)

        - anchor: hvis angitt, brukes for å filtrere relasjoner på ankernivå.
          Vi matcher:
            * rel.from_anchor == anchor hvis rel går ut fra source_id
            * rel.to_anchor == anchor hvis rel går inn til source_id
          Hvis relasjonen mangler to_anchor/from_anchor kan den fortsatt matches på dokumentnivå.

        - direction: "out" | "in" | "both"
        """
        sid = (source_id or "").strip()
        a = _norm_anchor(anchor)
        a_hierarchy = set(anchor_hierarchy(a)) if a else set()
        out: List[Tuple[str, Optional[str], str, Optional[str]]] = []

        for rel in self.relations:
            if direction in ("out", "both") and rel.from_id == sid:
                # D2: Hierarkisk match.
                # Hvis spørsmålet er mer spesifikt (f.eks. §1-1(1)[a]) skal relasjoner på §1-1(1)
                # eller §1-1 også matches.
                if a is not None and rel.from_anchor is not None and rel.from_anchor not in a_hierarchy:
                    continue
                out.append((rel.to_id, rel.to_anchor, rel.relation_type, rel.note))
            if direction in ("in", "both") and rel.to_id == sid:
                if a is not None and rel.to_anchor is not None and rel.to_anchor not in a_hierarchy:
                    continue
                out.append((rel.from_id, rel.from_anchor, rel.relation_type, rel.note))
        return out


def load_library(path: str | Path) -> Library:
    p = Path(path)
    if not p.exists():
        return Library()
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Library JSON må være et objekt på toppnivå")
    return Library.from_dict(data)


def save_library(library: Library, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(library.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
