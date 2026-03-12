from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from .anchors import anchor_hierarchy, extract_legal_anchor, normalize_anchor
from .kildebibliotek import Library, load_library


# Standard-ankere i spørsmål
# - "punkt 8" / "pkt 8" -> P8
PUNKT_RE = re.compile(r"\b(?:punkt|pkt\.?|avsnitt)\s*(\d{1,3})\b", re.IGNORECASE)
# - direkte "P8" (noen vil skrive dette selv)
P_DIRECT_RE = re.compile(r"\bP(\d{1,3}(?:\.\d+)*)\b", re.IGNORECASE)
# - application material "A1"
A_RE = re.compile(r"\bA(\d{1,3})\b", re.IGNORECASE)


class QueryableCollection(Protocol):
    def query(self, *, query_texts: List[str], n_results: int, where: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ...


def extract_anchor(text: str) -> Optional[str]:
    """Finn første "anker" i tekst/spørsmål.

    Prioritet:
      1) Lov/forskrift: §1-1, evt. ledd/bokstav ("§1-1(1)[a]")
      2) Standard-paragraf: P8 (fra "P8" eller "punkt/pkt 8")
      3) Application material: A1

    Merk:
      - Vi bruker ikke "ISA 230" som anker her. ISA-nr er dokument-identifikator,
        og håndteres via source_id + vanlig retrieval.
    """
    if not text:
        return None

    legal = extract_legal_anchor(text)
    if legal:
        return legal

    m2 = P_DIRECT_RE.search(text)
    if m2:
        return normalize_anchor(f"P{m2.group(1)}")

    m3 = PUNKT_RE.search(text)
    if m3:
        return normalize_anchor(f"P{m3.group(1)}")

    m4 = A_RE.search(text)
    if m4:
        return normalize_anchor(f"A{m4.group(1)}")

    return None


@dataclass(frozen=True)
class ContextChunk:
    text: str
    metadata: Dict[str, Any]
    chunk_id: Optional[str] = None


def _flatten_query_result(res: Dict[str, Any]) -> List[ContextChunk]:
    docs = (res.get("documents") or [[]])[0] or []
    metas = (res.get("metadatas") or [[]])[0] or []
    ids = (res.get("ids") or [[]])[0] or []
    out: List[ContextChunk] = []
    for i, doc in enumerate(docs):
        meta = dict(metas[i] or {}) if i < len(metas) else {}
        cid = ids[i] if i < len(ids) else None
        out.append(ContextChunk(text=str(doc or ""), metadata=meta, chunk_id=cid))
    return out


def _format_chunk(chunk: ContextChunk) -> str:
    meta = chunk.metadata or {}
    source_id = meta.get("source_id") or meta.get("source_title") or meta.get("file_name") or "KILDE"
    anchor = meta.get("anchor")
    header = f"[{source_id}{(' ' + anchor) if anchor else ''}]"  # e.g. [Revisorloven §1-1]
    return f"{header}\n{chunk.text.strip()}".strip()


def _chunk_key(c: ContextChunk) -> str:
    """Stabil dedup-key for chunks."""
    if c.chunk_id:
        return str(c.chunk_id)
    meta = c.metadata or {}
    return str(meta.get("source_path")) + "|" + str(meta.get("chunk_index"))


def _query_relation_chunks_with_anchor_fallback(
    collection: QueryableCollection,
    *,
    question: str,
    target_source_id: str,
    preferred_anchor: Optional[str],
    rel_n_results: int,
) -> List[ContextChunk]:
    """Hent chunks for et relatert dokument med anker-fallback.

    D2: Hvis vi spør på svært spesifikk anchor (f.eks. §1-1(1)[a]) men target-dokumentet
    kun har paragraf- eller leddankere, prøver vi automatisk foreldre-ankere:

        §1-1(1)[a] -> §1-1(1) -> §1-1

    Hvis ingenting finnes selv etter fallback, gjør vi et doc-nivå query på source_id.
    """
    target_id = (target_source_id or "").strip()
    if not target_id:
        return []

    pref = normalize_anchor(preferred_anchor)
    candidates = anchor_hierarchy(pref) if pref else []

    gathered: List[ContextChunk] = []
    seen: set[str] = set()

    def _add(chunks: List[ContextChunk]) -> None:
        for c in chunks:
            k = _chunk_key(c)
            if k in seen:
                continue
            seen.add(k)
            if c.text.strip():
                gathered.append(c)
            if len(gathered) >= rel_n_results:
                return

    # 1) Prøv med anker-filter (og foreldre)
    if candidates:
        for cand in candidates:
            where: Dict[str, Any] = {"source_id": target_id, "anchor": cand}
            res = collection.query(query_texts=[question], n_results=rel_n_results, where=where)
            chunks = _flatten_query_result(res)

            # Bakoverkompat: eldre indekser kan ha lagret standard-ankere uten P-prefiks.
            if (not chunks) and cand.startswith("P") and re.fullmatch(r"P\d{1,3}(?:\.\d+)*", cand):
                where2 = {"source_id": target_id, "anchor": cand[1:]}
                res2 = collection.query(query_texts=[question], n_results=rel_n_results, where=where2)
                chunks = _flatten_query_result(res2)

            _add(chunks)
            if len(gathered) >= rel_n_results:
                break

    # 2) Fallback: doc-nivå query dersom vi ikke fikk noe
    if not gathered:
        res = collection.query(query_texts=[question], n_results=rel_n_results, where={"source_id": target_id})
        gathered = _flatten_query_result(res)

    return gathered


def make_context(
    question: str,
    collection: QueryableCollection,
    *,
    n_results: int = 5,
    library_path: Optional[str | Path] = None,
    expand_relations: bool = True,
    rel_n_results: int = 2,
) -> Tuple[str, List[ContextChunk]]:
    """Henter RAG-kontekst + valgfri relasjonsbasert ekspansjon."""
    base_res = collection.query(query_texts=[question], n_results=n_results)
    base_chunks = _flatten_query_result(base_res)

    if not expand_relations:
        context = "\n\n".join(_format_chunk(c) for c in base_chunks if c.text.strip())
        return context, base_chunks

    # Finn anchor for ekspansjon
    anchor = extract_anchor(question)
    if not anchor:
        for c in base_chunks:
            a = c.metadata.get("anchor") if c.metadata else None
            if a:
                anchor = normalize_anchor(str(a))
                break

    if not anchor:
        context = "\n\n".join(_format_chunk(c) for c in base_chunks if c.text.strip())
        return context, base_chunks

    lib: Optional[Library] = None
    if library_path:
        try:
            lib = load_library(library_path)
        except Exception:
            lib = None

    if not lib or not lib.relations:
        context = "\n\n".join(_format_chunk(c) for c in base_chunks if c.text.strip())
        return context, base_chunks

    # Finn source_ids i base-resultatene
    source_ids: List[str] = []
    for c in base_chunks:
        sid = (c.metadata or {}).get("source_id")
        if sid and sid not in source_ids:
            source_ids.append(str(sid))

    expanded: List[ContextChunk] = []
    for sid in source_ids:
        for (target_id, target_anchor, _rtype, _note) in lib.related_targets(sid, anchor=anchor, direction="both"):
            preferred = normalize_anchor(target_anchor or anchor or "")
            rel_chunks = _query_relation_chunks_with_anchor_fallback(
                collection,
                question=question,
                target_source_id=target_id,
                preferred_anchor=preferred,
                rel_n_results=rel_n_results,
            )
            expanded.extend(rel_chunks)

    # Dedup på chunk_id hvis mulig
    seen: set[str] = set()
    final: List[ContextChunk] = []
    for c in base_chunks + expanded:
        key = _chunk_key(c)
        if key in seen:
            continue
        seen.add(key)
        if c.text.strip():
            final.append(c)

    context = "\n\n".join(_format_chunk(c) for c in final)
    return context, final
