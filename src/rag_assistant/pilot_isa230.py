from __future__ import annotations

"""rag_assistant.pilot_isa230

Små, *testbare* hjelpefunksjoner for å gjøre det enkelt å kjøre en pilot
med ISA 230 i dette repoet.

Mål (pilot):
----------------
- Gjøre det lett å starte med én standard (ISA 230)
- Mulighet til å inkludere lov/forskrift hvis de finnes (RL/RF)
- Filtrere bibliotek og relasjoner til et lite scope (raskere indeks + enklere eval)

Denne modulen inneholder *ingen* kall mot OpenAI eller Chroma direkte.
Det gjør at vi kan teste logikken uten nett.
"""

from dataclasses import dataclass
from typing import Iterable, List, Sequence

from .kildebibliotek import Library, Relation, Source


DEFAULT_REQUIRED_SOURCE_IDS: tuple[str, ...] = ("ISA-230",)
DEFAULT_OPTIONAL_SOURCE_IDS: tuple[str, ...] = ("RL", "RF")


def missing_source_ids(library: Library, source_ids: Sequence[str]) -> List[str]:
    missing: List[str] = []
    for sid in source_ids:
        if not library.get_source(sid):
            missing.append(sid)
    return missing


def choose_pilot_source_ids(
    library: Library,
    *,
    required: Sequence[str] = DEFAULT_REQUIRED_SOURCE_IDS,
    optional: Sequence[str] = DEFAULT_OPTIONAL_SOURCE_IDS,
    include_optional: bool = True,
) -> List[str]:
    """Returnerer en liste med kilde-id-er som finnes i biblioteket.

    - Required (default: ISA-230) tas alltid med hvis den finnes.
    - Optional (default: RL/RF) tas med hvis include_optional og de finnes.
    """
    ids: List[str] = []
    for sid in required:
        if library.get_source(sid):
            ids.append(sid)

    if include_optional:
        for sid in optional:
            if library.get_source(sid) and sid not in ids:
                ids.append(sid)
    return ids


def _filter_sources(sources: Iterable[Source], allowed: set[str]) -> List[Source]:
    out: List[Source] = []
    for s in sources:
        if s.id in allowed:
            out.append(s)
    # stabil sort for deterministiske tester
    return sorted(out, key=lambda x: x.id)


def _filter_relations(relations: Iterable[Relation], allowed: set[str]) -> List[Relation]:
    out: List[Relation] = []
    for r in relations:
        if r.from_id in allowed and r.to_id in allowed:
            out.append(r)
    return out


def subset_library_to_sources(library: Library, source_ids: Sequence[str]) -> Library:
    """Lager et nytt Library med kun angitte kilder og relasjoner innenfor scope."""
    allowed = {sid for sid in source_ids if sid}
    return Library(
        version=library.version,
        sources=_filter_sources(library.sources, allowed),
        relations=_filter_relations(library.relations, allowed),
    )


@dataclass(frozen=True)
class PilotScope:
    """Lite datasett som beskriver pilot-scope."""

    source_ids: List[str]
    missing_required: List[str]


def build_default_scope(library: Library, *, include_optional: bool = True) -> PilotScope:
    """Bygger et standard pilot-scope for ISA 230.

    missing_required inkluderer evt. manglende `DEFAULT_REQUIRED_SOURCE_IDS`.
    """
    required = list(DEFAULT_REQUIRED_SOURCE_IDS)
    missing = missing_source_ids(library, required)
    ids = choose_pilot_source_ids(library, include_optional=include_optional)
    return PilotScope(source_ids=ids, missing_required=missing)
