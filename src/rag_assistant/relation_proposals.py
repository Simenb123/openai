from __future__ import annotations

"""rag_assistant.relation_proposals

Semi-automatisk forslag til relasjoner.

D5-fokus:
- Brukeren velger *Fra-kilde* og *Til-kilde* i GUI.
- Systemet skanner tekst i Fra-kilden og leter etter anker-referanser som passer Til-kildens doc_type.
  Eksempel:
    - Til = LOV/FORSKRIFT: finn "§ ..." (og prøv å fange ledd/bokstav)
    - Til = ISA/ISQM: finn "P8", "punkt 8", "A1" osv.

- Resultatet presenteres som en liste med forslag som kan godkjennes og legges inn som relasjoner.

Begrensninger:
- Heuristikk. Treffer ikke alt.
- For ISA->lov vil standardene ofte ikke referere til paragraf direkte; da får du ofte kun doc-level forslag.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .anchor_validation import anchors_for_source
from .anchors import normalize_anchor
from .document_ingestor import DocumentIngestor
from .file_ingest import split_anchored_sections
from .kildebibliotek import Library, Relation
from .reference_extraction import extract_anchor_refs_for_doc_type, make_snippet
from .relation_suggestions import suggest_relation_types

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProposedRelation:
    relation: Relation
    occurrences: int
    known_target_anchor: bool
    evidence: str


@dataclass(frozen=True)
class ProposalResult:
    proposals: List[ProposedRelation]
    warnings: List[str]


def _resolve_file(base_dir: Path, file_path: str) -> Path:
    p = Path(file_path)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _target_anchor_set(anchor_inventory: Dict[str, Any], target_source_id: str) -> set[str]:
    anchors = anchors_for_source(anchor_inventory, target_source_id)
    return {normalize_anchor(a) or a for a in anchors if (normalize_anchor(a) or a)}


def propose_relations_for_pair(
    library: Library,
    *,
    from_source_id: str,
    to_source_id: str,
    anchor_inventory: Dict[str, Any],
    base_dir: str | Path,
    max_proposals: int = 200,
    include_unknown_anchors: bool = True,
    fallback_doc_level: bool = True,
) -> ProposalResult:
    """Skanner Fra-kildens tekst og foreslår relasjoner til Til-kilden."""
    warnings: List[str] = []
    from_id = (from_source_id or "").strip()
    to_id = (to_source_id or "").strip()
    if not from_id or not to_id:
        return ProposalResult([], ["Fra og Til må være valgt"])

    from_src = library.get_source(from_id)
    to_src = library.get_source(to_id)
    if not from_src or not to_src:
        return ProposalResult([], ["Ugyldig Fra/Til: kilde finnes ikke i biblioteket"])

    base = Path(base_dir)

    target_anchors = _target_anchor_set(anchor_inventory, to_id)
    to_doc_type = (to_src.doc_type or "OTHER").strip().upper()
    from_doc_type = (from_src.doc_type or "OTHER").strip().upper()

    suggested_types = suggest_relation_types(from_doc_type, to_doc_type)
    default_rel_type = suggested_types[0] if suggested_types else "RELATES_TO"

    ing = DocumentIngestor()

    # aggregator: rel.key() -> (Relation, count, known, evidence)
    agg: Dict[str, Tuple[Relation, int, bool, str]] = {}

    def _add(rel: Relation, *, known: bool, evidence: str) -> None:
        key = rel.key()
        if key in agg:
            r0, c0, known0, ev0 = agg[key]
            agg[key] = (r0, c0 + 1, known0 or known, ev0 or evidence)
        else:
            agg[key] = (rel, 1, known, evidence)

    # Skann alle filer i from_src
    for fp in (from_src.files or []):
        try:
            p = _resolve_file(base, fp)
            doc = ing.parse_file(p)
        except Exception as e:
            msg = f"Kunne ikke lese {fp}: {e}"
            logger.warning(msg)
            warnings.append(msg)
            continue

        sections = split_anchored_sections(doc.text)
        for from_anchor, section_text in sections:
            a_from = normalize_anchor(from_anchor) if from_anchor else None

            refs = extract_anchor_refs_for_doc_type(section_text, to_doc_type)
            if not refs:
                continue

            for ref in refs:
                a_to = normalize_anchor(ref.anchor) or ref.anchor
                known = a_to in target_anchors if target_anchors else False
                if (not include_unknown_anchors) and (not known):
                    continue

                # note/evidence
                snippet = make_snippet(section_text, ref.start, ref.end)
                ev = f"{(Path(fp).name)}: {snippet}" if snippet else Path(fp).name

                rel = Relation(
                    from_id=from_id,
                    to_id=to_id,
                    relation_type=default_rel_type,
                    from_anchor=a_from,
                    to_anchor=a_to,
                    note=f"Auto-forslag (skann): {ev}" if ev else "Auto-forslag (skann)",
                )
                _add(rel, known=known, evidence=ev)

    proposals: List[ProposedRelation] = []
    for rel, count, known, evidence in agg.values():
        proposals.append(ProposedRelation(relation=rel, occurrences=count, known_target_anchor=known, evidence=evidence))

    # Fallback: hvis ingen konkrete ankere ble funnet, gi doc-level forslag
    if not proposals and fallback_doc_level:
        rel = Relation(
            from_id=from_id,
            to_id=to_id,
            relation_type=default_rel_type,
            from_anchor=None,
            to_anchor=None,
            note="Auto-forslag: Ingen eksplisitte anker-referanser funnet ved skann. Doc-level relasjon kan likevel være nyttig.",
        )
        proposals.append(ProposedRelation(relation=rel, occurrences=1, known_target_anchor=True, evidence="(ingen anker)"))

    # Sorter: kjente ankere først, flest forekomster, deretter anchor tekst
    proposals.sort(
        key=lambda p: (
            0 if p.known_target_anchor else 1,
            -p.occurrences,
            p.relation.from_anchor or "",
            p.relation.to_anchor or "",
        )
    )
    if len(proposals) > max_proposals:
        proposals = proposals[:max_proposals]
        warnings.append(f"For mange forslag, viser kun første {max_proposals}")

    return ProposalResult(proposals=proposals, warnings=warnings)
