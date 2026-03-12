from __future__ import annotations

"""rag_assistant.reference_extraction

Best-effort ekstraksjon av referanser/ankere fra tekst.

Dette brukes i D5 til *semi-automatisk forslag til relasjoner*:
- Skann "Fra"-kildens tekst for referanser som ser ut som ankere i "Til"-kilden.
- F.eks. hvis Til er LOV/FORSKRIFT: finn alle "§ ..." i teksten.
- Hvis Til er ISA/ISQM: finn "P8", "punkt 8", "A1" osv.

Merk:
- Dette er heuristikk. Det vil alltid finnes falske positive/negative.
- Vi prioriterer robusthet + enkelhet + testbarhet.
"""

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence

from .anchors import extract_legal_anchor, normalize_anchor


@dataclass(frozen=True)
class ExtractedAnchorRef:
    anchor: str
    start: int
    end: int
    raw: str


# Juridisk: § 1-1 osv.
_LEGAL_PAR_RE = re.compile(r"§\s*\d+(?:-\d+)*[A-Za-z]?", re.IGNORECASE)

# Standard: P8, P1.2, A1
_P_DIRECT_RE = re.compile(r"\bP(\d{1,3}(?:\.\d+)*)\b", re.IGNORECASE)
_A_DIRECT_RE = re.compile(r"\bA(\d{1,3})\b", re.IGNORECASE)
_PUNKT_RE = re.compile(r"\b(?:punkt|pkt\.?|avsnitt)\s*(\d{1,3}(?:\.\d+)*)\b", re.IGNORECASE)


def extract_all_legal_anchors(text: str, *, tail_chars: int = 120) -> List[ExtractedAnchorRef]:
    """Ekstraherer alle juridiske ankere (best-effort).

    Strategi:
    - Finn alle forekomster av "§ <nr>" med regex.
    - For hvert treff: bruk anchors.extract_legal_anchor() på et lite segment for å fange ledd/bokstav.
    """
    if not text:
        return []

    out: List[ExtractedAnchorRef] = []
    for m in _LEGAL_PAR_RE.finditer(text):
        start, end = m.start(), m.end()
        seg_end = min(len(text), end + max(0, int(tail_chars)))

        segment = text[start:seg_end]

        # Klipp segmentet hvis en ny paragraf-referanse dukker opp rett etter (for å unngå feil ledd/bokstav)
        if len(segment) > (end - start):
            m2 = _LEGAL_PAR_RE.search(segment[(end - start) :])
            if m2:
                segment = segment[: (end - start) + m2.start()]

        a = extract_legal_anchor(segment, tail_chars=tail_chars)
        if not a:
            continue
        na = normalize_anchor(a) or a
        out.append(ExtractedAnchorRef(anchor=na, start=start, end=end, raw=m.group(0)))
    return out


def extract_all_standard_anchors(text: str) -> List[ExtractedAnchorRef]:
    """Ekstraherer P/A-ankere fra tekst (best-effort)."""
    if not text:
        return []

    out: List[ExtractedAnchorRef] = []

    for m in _P_DIRECT_RE.finditer(text):
        a = normalize_anchor(f"P{m.group(1)}")
        if a:
            out.append(ExtractedAnchorRef(anchor=a, start=m.start(), end=m.end(), raw=m.group(0)))

    for m in _A_DIRECT_RE.finditer(text):
        a = normalize_anchor(f"A{m.group(1)}")
        if a:
            out.append(ExtractedAnchorRef(anchor=a, start=m.start(), end=m.end(), raw=m.group(0)))

    for m in _PUNKT_RE.finditer(text):
        a = normalize_anchor(f"P{m.group(1)}")
        if a:
            out.append(ExtractedAnchorRef(anchor=a, start=m.start(), end=m.end(), raw=m.group(0)))

    # dedup på (anchor,start,end) - men behold rekkefølge
    seen = set()
    dedup: List[ExtractedAnchorRef] = []
    for r in out:
        k = (r.anchor, r.start, r.end)
        if k in seen:
            continue
        seen.add(k)
        dedup.append(r)
    return dedup


def extract_anchor_refs_for_doc_type(text: str, doc_type: str) -> List[ExtractedAnchorRef]:
    """Returnerer anker-referanser avhengig av target doc_type."""
    dt = (doc_type or "OTHER").strip().upper()
    if dt in {"LOV", "FORSKRIFT"}:
        return extract_all_legal_anchors(text)
    if dt in {"ISA", "ISQM"}:
        return extract_all_standard_anchors(text)
    return []


def make_snippet(text: str, start: int, end: int, *, max_len: int = 200) -> str:
    """Lager et lite utdrag rundt en posisjon i tekst."""
    if not text:
        return ""
    start = max(0, int(start))
    end = max(start, int(end))

    left = max(0, start - 60)
    right = min(len(text), end + 120)
    snippet = text[left:right]
    snippet = re.sub(r"\s+", " ", snippet).strip()
    if len(snippet) > max_len:
        snippet = snippet[: max_len - 1].rstrip() + "…"
    return snippet
