from __future__ import annotations

"""rag_assistant.relation_mapping

Hjelpefunksjoner for systematisk relasjonsbygging på ankernivå.

Denne modulen er bevisst *uten GUI* slik at den kan testes med pytest.

Per D6 bruker vi dette til å gi "kandidatankere" i en kartleggings-wizard:
- Velg et fra-anker
- Få forslag til relevante til-ankere (prefix/hierarki-basert)

Eksempler:
- Fra: §1-1(1)[a] -> forslag: §1-1(1)[a], §1-1(1), §1-1, ...
- Fra: §1 -> forslag: §1-1, §1-2, ... (alle som starter med §1)
- Fra: P8 -> forslag: P8, P8.1, P8.2, ...
"""

from typing import Dict, Iterable, List, Sequence, Set

from .anchors import anchor_hierarchy, normalize_anchor
from .kildebibliotek import Relation


def _norm(a: str) -> str:
    return normalize_anchor(a) or (a or "").strip()


def suggest_target_anchors(
    from_anchor: str,
    target_anchors: Sequence[str],
    *,
    max_results: int = 80,
) -> List[str]:
    """Foreslår target-ankere basert på fra-anker.

    Strategi (best-effort):
    1) Normaliser fra_anker
    2) Bruk anchor_hierarchy(fra) (fra -> foreldre)
    3) For hver nivå i hierarkiet: finn target ankere som
       - er lik nivået, eller
       - starter med nivået (prefix-match)

    Returnerer en dedupet liste i prioritert rekkefølge.
    """
    fa = _norm(from_anchor)
    if not fa:
        return []

    # Normaliser target
    norm_targets: List[str] = []
    for a in target_anchors:
        na = _norm(a)
        if na:
            norm_targets.append(na)

    # Index på første tegn for å redusere scanning litt
    buckets: dict[str, list[str]] = {}
    for t in norm_targets:
        buckets.setdefault(t[:1], []).append(t)

    candidates: List[str] = []
    seen = set()

    # Hierarki: [fa, parent1, parent2, ...]
    levels = anchor_hierarchy(fa) or [fa]

    for lvl in levels:
        first = lvl[:1]
        pool = buckets.get(first, norm_targets)

        # eksakt match først
        for t in pool:
            if t == lvl and t not in seen:
                seen.add(t)
                candidates.append(t)
                if len(candidates) >= max_results:
                    return candidates

        # prefix-match
        for t in pool:
            if t != lvl and t.startswith(lvl) and t not in seen:
                seen.add(t)
                candidates.append(t)
                if len(candidates) >= max_results:
                    return candidates

    return candidates


def apply_suggestions_to_ordered_list(
    all_targets: Sequence[str],
    suggestions: Iterable[str],
    *,
    max_results: int = 80,
) -> List[str]:
    """Tar forslag og returnerer dem i samme rekkefølge som `all_targets`.

    Dette er praktisk for GUI der vi vil auto-velge forslag i en listbox.
    """
    sset = {(_norm(s) or s) for s in suggestions if (_norm(s) or s)}
    out: List[str] = []
    for a in all_targets:
        na = _norm(a)
        if na and na in sset:
            out.append(na)
            if len(out) >= max_results:
                break
    return out


# ---------------- mapping state helpers (D8) ----------------


def relations_between(relations: Iterable[Relation], from_id: str, to_id: str) -> List[Relation]:
    """Filtrer relasjoner for et (from_id, to_id)-par."""
    fid = (from_id or "").strip()
    tid = (to_id or "").strip()
    if not fid or not tid:
        return []
    return [r for r in relations if r.from_id == fid and r.to_id == tid]


def group_relations_by_from_anchor(
    relations: Iterable[Relation],
    from_id: str,
    to_id: str,
) -> Dict[str, List[Relation]]:
    """Grupper relasjoner for et par på `from_anchor`.

    Kun ankernivå-relasjoner inkluderes:
    - r.from_anchor må være satt
    - r.to_anchor må være satt

    Dette brukes i GUI for å vise "hva er allerede koblet" for valgt fra-anker.
    """
    out: Dict[str, List[Relation]] = {}
    for r in relations_between(relations, from_id, to_id):
        if not r.from_anchor or not r.to_anchor:
            continue
        out.setdefault(r.from_anchor, []).append(r)

    # Stabil sortering for konsistent visning
    for k, lst in list(out.items()):
        out[k] = sorted(lst, key=lambda x: (x.to_anchor or "", x.relation_type))
    return out


def mapped_from_anchors(relations: Iterable[Relation], from_id: str, to_id: str) -> Set[str]:
    """Returnerer mengden fra-ankere som har minst én ankernivå-relasjon."""
    grouped = group_relations_by_from_anchor(relations, from_id, to_id)
    return set(grouped.keys())


def to_anchors_for_from_anchor(
    relations: Iterable[Relation],
    from_id: str,
    to_id: str,
    from_anchor: str,
) -> List[str]:
    """Hent unike to-ankere for et gitt fra-anker (ankernivå)."""
    fid = (from_id or "").strip()
    tid = (to_id or "").strip()
    fa = _norm(from_anchor)
    if not fid or not tid or not fa:
        return []

    out: List[str] = []
    seen = set()
    for r in relations_between(relations, fid, tid):
        if r.from_anchor != fa:
            continue
        if not r.to_anchor:
            continue
        if r.to_anchor in seen:
            continue
        seen.add(r.to_anchor)
        out.append(r.to_anchor)
    return out
