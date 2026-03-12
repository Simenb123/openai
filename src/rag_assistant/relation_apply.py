from __future__ import annotations

"""rag_assistant.relation_apply

Pure (GUI-uavhengig) logikk for å *bruke* en relasjonsimport.

Hvorfor en egen modul?
----------------------
D10 introduserte import/eksport av relasjoner fra GUI.
I praksis trenger vi også:
- patch-semantikk ved merge (ikke røre uendrede relasjoner)
- deterministisk atferd og god testdekning

Denne modulen brukes av GUI-importen i D11, men kan også brukes direkte fra
scripts/tester.
"""

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .kildebibliotek import Relation
from .relation_diff import RelationDiff, compute_relation_diff, dedupe_relations


@dataclass(frozen=True)
class RelationImportApplyResult:
    """Resultat fra apply_relation_import."""

    mode: str
    scope_pair: Optional[Tuple[str, str]]
    ignored_outside_scope: int
    diff: RelationDiff
    new_relations: List[Relation]


def _in_pair(r: Relation, pair: Tuple[str, str]) -> bool:
    return r.from_id == pair[0] and r.to_id == pair[1]


def apply_relation_import(
    existing_all: Iterable[Relation],
    incoming_all: Iterable[Relation],
    *,
    mode: str,
    scope_pair: Optional[Tuple[str, str]] = None,
) -> RelationImportApplyResult:
    """Bruk (apply) en import av relasjoner.

    Parametre
    ---------
    existing_all:
        Hele nåværende relasjonsliste (typisk library.relations).

    incoming_all:
        Relasjoner lest fra fil.

    mode:
        "merge" eller "replace"

    scope_pair:
        None => global apply.
        (from_id, to_id) => apply kun for det paret.

    Semantikk
    ---------
    - merge: patch-semantikk. Vi oppdaterer/legger til kun relasjoner som er
      nye eller har endret note. Uendrede relasjoner røres ikke.

    - replace:
        - global: erstatter hele relasjonslisten med innkommende (dedupet)
        - pair: fjerner alle relasjoner i paret, og legger inn innkommende for paret

    Returnerer
    ----------
    RelationImportApplyResult med diff og ny relasjonsliste.
    """

    m = (mode or "").strip().lower()
    if m not in ("merge", "replace"):
        raise ValueError("mode må være 'merge' eller 'replace'")

    existing_list = list(existing_all)
    incoming_list = list(incoming_all)

    ignored = 0
    if scope_pair is not None:
        incoming_scoped = [r for r in incoming_list if _in_pair(r, scope_pair)]
        ignored = len(incoming_list) - len(incoming_scoped)
        existing_scope = [r for r in existing_list if _in_pair(r, scope_pair)]
    else:
        incoming_scoped = incoming_list
        existing_scope = existing_list

    # Dedupe incoming (siste forekomst vinner)
    incoming_unique_map = dedupe_relations(incoming_scoped)
    incoming_unique = list(incoming_unique_map.values())

    # Diff beregnes på *rå* incoming_scoped (incoming_total beholder antall rader i fil)
    diff = compute_relation_diff(existing_scope, incoming_scoped)

    # Hvis ingen endringer i det hele tatt, returner original liste (for stabilitet)
    if m == "merge" and not diff.added and not diff.updated:
        return RelationImportApplyResult(
            mode=m,
            scope_pair=scope_pair,
            ignored_outside_scope=ignored,
            diff=diff,
            new_relations=existing_list,
        )

    if m == "replace" and not diff.added and not diff.updated and not diff.removed:
        return RelationImportApplyResult(
            mode=m,
            scope_pair=scope_pair,
            ignored_outside_scope=ignored,
            diff=diff,
            new_relations=existing_list,
        )

    if m == "merge":
        # Patch: oppdater i place (beholder posisjon), legg til nye på slutten
        out = list(existing_list)
        index = {r.key(): i for i, r in enumerate(out)}

        changes: List[Relation] = []
        changes.extend(diff.added)
        changes.extend([u.new for u in diff.updated])

        for r in changes:
            k = r.key()
            if k in index:
                out[index[k]] = r
            else:
                index[k] = len(out)
                out.append(r)

        return RelationImportApplyResult(
            mode=m,
            scope_pair=scope_pair,
            ignored_outside_scope=ignored,
            diff=diff,
            new_relations=out,
        )

    # replace
    if scope_pair is None:
        out = list(incoming_unique)
    else:
        pair = scope_pair
        out = [r for r in existing_list if not _in_pair(r, pair)]
        out.extend(incoming_unique)

    return RelationImportApplyResult(
        mode=m,
        scope_pair=scope_pair,
        ignored_outside_scope=ignored,
        diff=diff,
        new_relations=out,
    )
