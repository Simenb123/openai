from __future__ import annotations

"""rag_assistant.relation_diff

Diff/forhåndsvisning for relasjonsimport.

Motivasjon
----------
Når relasjonskartet blir stort, vil du ofte:
  - importere relasjoner fra CSV/JSON,
  - se hva som faktisk kommer til å endre seg,
  - velge *merge/upsert* eller *replace* med trygghet.

Denne modulen er GUI-uavhengig og testbar med pytest.

Begreper
--------
- "key" for relasjon er definert av Relation.key() (note inngår ikke i nøkkelen).
- En "update" betyr at nøkkel allerede finnes, men at note endres.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple

from .kildebibliotek import Relation


@dataclass(frozen=True)
class RelationDiffSummary:
    existing_total: int
    incoming_total: int
    incoming_unique: int
    added: int
    updated: int
    unchanged: int
    removed: int
    sample_added: List[str]
    sample_updated: List[str]
    sample_removed: List[str]


@dataclass(frozen=True)
class RelationUpdate:
    """En oppdatering av note for en eksisterende relasjon."""

    old: Relation
    new: Relation


@dataclass(frozen=True)
class RelationDiff:
    """Detaljert diff mellom eksisterende og innkommende relasjoner."""

    existing_total: int
    incoming_total: int
    incoming_unique: int
    added: List[Relation]
    updated: List[RelationUpdate]
    unchanged: List[Relation]
    removed: List[Relation]

    def changed_count(self) -> int:
        return len(self.added) + len(self.updated) + len(self.removed)


def dedupe_relations(relations: Iterable[Relation]) -> Dict[str, Relation]:
    """Deduper relasjoner på nøkkel.

    Hvis samme nøkkel forekommer flere ganger, beholdes siste forekomst.
    Rekkefølge: vi forsøker å la *siste forekomst* styre rekkefølgen, slik at
    eksport/import fra Excel oppleves mer intuitivt.
    """
    out: Dict[str, Relation] = {}
    for r in relations:
        k = r.key()
        if k in out:
            # flytt nøkkelen til slutten (siste forekomst)
            del out[k]
        out[k] = r
    return out


def _short(r: Relation) -> str:
    fa = r.from_anchor or ""
    ta = r.to_anchor or ""
    return f"{r.from_id} {fa} {r.relation_type} {r.to_id} {ta}".strip()


def compute_relation_diff_summary(
    existing: Iterable[Relation],
    incoming: Iterable[Relation],
    *,
    sample_limit: int = 8,
) -> RelationDiffSummary:
    """Beregner en lettlest diff mellom eksisterende og innkommende relasjoner.

    - "added": nøkkel finnes ikke fra før.
    - "updated": nøkkel finnes, men note endres.
    - "unchanged": nøkkel finnes og note er lik.
    - "removed": eksisterende nøkkel finnes ikke i innkommende (relevant ved replace).
    """
    existing_list = list(existing)
    incoming_list = list(incoming)

    ex = {r.key(): r for r in existing_list}
    inc = dedupe_relations(incoming_list)

    added_keys: List[str] = []
    updated_pairs: List[Tuple[Relation, Relation]] = []
    unchanged_keys: List[str] = []

    for k, new in inc.items():
        old = ex.get(k)
        if old is None:
            added_keys.append(k)
        else:
            if (old.note or None) != (new.note or None):
                updated_pairs.append((old, new))
            else:
                unchanged_keys.append(k)

    removed_keys = [k for k in ex.keys() if k not in inc]

    # stable ordering for samples
    added_keys_sorted = sorted(added_keys)
    removed_keys_sorted = sorted(removed_keys)
    updated_pairs_sorted = sorted(updated_pairs, key=lambda p: p[0].key())

    sample_added = [_short(inc[k]) for k in added_keys_sorted[:sample_limit]]
    sample_removed = [_short(ex[k]) for k in removed_keys_sorted[:sample_limit]]
    sample_updated: List[str] = []
    for old, new in updated_pairs_sorted[:sample_limit]:
        o = (old.note or "").strip()
        n = (new.note or "").strip()
        # kort linje, men med note-diff
        if o and n:
            sample_updated.append(f"{_short(new)}  note: '{o}' → '{n}'")
        elif (not o) and n:
            sample_updated.append(f"{_short(new)}  note: (tom) → '{n}'")
        elif o and (not n):
            sample_updated.append(f"{_short(new)}  note: '{o}' → (tom)")
        else:
            sample_updated.append(f"{_short(new)}")

    return RelationDiffSummary(
        existing_total=len(existing_list),
        incoming_total=len(incoming_list),
        incoming_unique=len(inc),
        added=len(added_keys),
        updated=len(updated_pairs),
        unchanged=len(unchanged_keys),
        removed=len(removed_keys),
        sample_added=sample_added,
        sample_updated=sample_updated,
        sample_removed=sample_removed,
    )


def compute_relation_diff(existing: Iterable[Relation], incoming: Iterable[Relation]) -> RelationDiff:
    """Beregner en detaljert diff.

    - incoming dedupes på nøkkel (siste forekomst vinner)
    - "unchanged" refererer til innkommende relasjon (etter dedupe)
    """
    existing_list = list(existing)
    incoming_list = list(incoming)

    ex = {r.key(): r for r in existing_list}
    inc = dedupe_relations(incoming_list)

    added: List[Relation] = []
    updated: List[RelationUpdate] = []
    unchanged: List[Relation] = []

    for k, new in inc.items():
        old = ex.get(k)
        if old is None:
            added.append(new)
        else:
            if (old.note or None) != (new.note or None):
                updated.append(RelationUpdate(old=old, new=new))
            else:
                unchanged.append(new)

    removed = [ex[k] for k in ex.keys() if k not in inc]

    # Stabil sortering for visning
    added = sorted(added, key=lambda r: r.key())
    unchanged = sorted(unchanged, key=lambda r: r.key())
    updated = sorted(updated, key=lambda u: u.old.key())
    removed = sorted(removed, key=lambda r: r.key())

    return RelationDiff(
        existing_total=len(existing_list),
        incoming_total=len(incoming_list),
        incoming_unique=len(inc),
        added=added,
        updated=updated,
        unchanged=unchanged,
        removed=removed,
    )
