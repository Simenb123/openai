from __future__ import annotations

"""rag_assistant.gui.filtering

Små, testbare filterfunksjoner for GUI-lister.

Mål:
- Brukeren skal raskt kunne finne kilder/relasjoner uten å bla.
- Implementasjonen skal være enkel, robust og lett å teste.

Filter-logikk:
- Vi splitter query i tokens (whitespace).
- Alle tokens må finnes (AND) i en samlet "haystack"-streng.
- Matching er case-insensitiv substring.

Dette gir en god "fuzzy nok" opplevelse uten kompleks søk-syntaks.
"""

import re
from typing import Iterable, List, Sequence

from ..kildebibliotek import Relation, Source


_WS_RE = re.compile(r"\s+")


def tokenize_query(query: str) -> List[str]:
    q = (query or "").strip().lower()
    if not q:
        return []
    return [t for t in _WS_RE.split(q) if t]


def _matches_tokens(haystack: str, tokens: Sequence[str]) -> bool:
    if not tokens:
        return True
    h = (haystack or "").lower()
    return all(t in h for t in tokens)


def source_haystack(src: Source) -> str:
    tags = " ".join(src.tags or [])
    files = " ".join(src.files or [])
    return f"{src.id} {src.doc_type} {src.title} {tags} {files}".strip()


def relation_haystack(rel: Relation) -> str:
    return " ".join(
        [
            rel.from_id,
            rel.from_anchor or "",
            rel.relation_type,
            rel.to_id,
            rel.to_anchor or "",
            rel.note or "",
        ]
    ).strip()


def filter_sources(sources: Iterable[Source], query: str) -> List[Source]:
    tokens = tokenize_query(query)
    if not tokens:
        return list(sources)
    out: List[Source] = []
    for s in sources:
        if _matches_tokens(source_haystack(s), tokens):
            out.append(s)
    return out


def filter_relations(relations: Iterable[Relation], query: str) -> List[Relation]:
    tokens = tokenize_query(query)
    if not tokens:
        return list(relations)
    out: List[Relation] = []
    for r in relations:
        if _matches_tokens(relation_haystack(r), tokens):
            out.append(r)
    return out
