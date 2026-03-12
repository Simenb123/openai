from __future__ import annotations

"""rag_assistant.relation_templates

Relasjonsmaler (templates) for rask og konsistent relasjonsbygging.

Hvorfor maler?
- I praksis finnes det noen veldig typiske koblinger mellom dokumenttyper:
    * FORSKRIFT -> LOV  (hjemmel/presisering)
    * FORARBEID -> LOV  (forarbeid til)
    * DOM -> LOV/FORSKRIFT (tolkning/praksis)
    * TILSYN -> (LOV/FORSKRIFT/ISA/ISQM) (tilsyn av)
    * KOMMENTAR/ARTIKKEL -> (regelverk) (kommentar/veiledning)
    * INSTRUKS -> (regelverk) (praktisk veiledning)
    * ISA/ISQM -> LOV/FORSKRIFT (gjelder for / relevant for)

- Maler gjør at brukeren kan trykke "Bruk mal" og få:
    * anbefalt relasjonstype
    * anbefalt retning (ev. auto-bytte fra/til)
    * standard notat som kan tilpasses

Dette er et *hjelpe-lag* i GUI. Bibliotekformatet endres ikke.
"""

from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from .relation_suggestions import relation_type_label


def _norm_doc_type(v: Optional[str]) -> str:
    return (v or "OTHER").strip().upper() or "OTHER"


@dataclass(frozen=True)
class RelationTemplate:
    key: str
    label_no: str
    description_no: str
    from_doc_types: Tuple[str, ...]
    to_doc_types: Tuple[str, ...]
    relation_type: str
    default_note: str = ""
    allow_reverse: bool = True

    def match_direction(self, from_doc_type: str, to_doc_type: str) -> Optional[str]:
        """Returnerer 'forward', 'reverse' eller None."""
        f = _norm_doc_type(from_doc_type)
        t = _norm_doc_type(to_doc_type)
        if f in self.from_doc_types and t in self.to_doc_types:
            return "forward"
        if self.allow_reverse and (f in self.to_doc_types and t in self.from_doc_types):
            return "reverse"
        return None


@dataclass(frozen=True)
class ApplicableTemplate:
    template: RelationTemplate
    direction: str  # 'forward' eller 'reverse'


_TEMPLATES: List[RelationTemplate] = [
    RelationTemplate(
        key="FORSKRIFT_HJEMLET_I_LOV",
        label_no="Forskrift hjemlet i lov",
        description_no="Brukes når en forskrift er gitt med hjemmel i en lov.",
        from_doc_types=("FORSKRIFT",),
        to_doc_types=("LOV",),
        relation_type="AUTHORIZED_BY",
        default_note="Forskriften er gitt med hjemmel i loven.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="FORARBEID_TIL_LOV",
        label_no="Forarbeid til lov",
        description_no="Brukes når dokumentet er forarbeid (Prop./Ot.prp./NOU) til en lov.",
        from_doc_types=("FORARBEID",),
        to_doc_types=("LOV",),
        relation_type="PREPARATORY_WORKS_FOR",
        default_note="Forarbeid til loven.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="DOM_TOLKER_REGELVERK",
        label_no="Dom tolker regelverk",
        description_no="Brukes når en dom tolker/anvender lov/forskrift (praksis).",
        from_doc_types=("DOM",),
        to_doc_types=("LOV", "FORSKRIFT"),
        relation_type="INTERPRETS",
        default_note="Dommen illustrerer/tolker regelverket i praksis.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="TILSYN_VURDERER_ETTERLEVELSE",
        label_no="Tilsyn vurderer etterlevelse",
        description_no="Brukes når en tilsynsrapport vurderer etterlevelse av lov/forskrift/standard.",
        from_doc_types=("TILSYN",),
        to_doc_types=("LOV", "FORSKRIFT", "ISA", "ISQM"),
        relation_type="SUPERVISION_OF",
        default_note="Tilsynets vurderinger knyttet til etterlevelse.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="KOMMENTAR_TIL_REGELVERK",
        label_no="Kommentar til regelverk",
        description_no="Brukes for lovkommentar, veiledning eller fagartikkel om regelverket.",
        from_doc_types=("KOMMENTAR", "ARTIKKEL"),
        to_doc_types=("LOV", "FORSKRIFT", "ISA", "ISQM"),
        relation_type="COMMENTARY_ON",
        default_note="Kommentar/veiledning til regelverket.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="INSTRUKS_VEILEDNING",
        label_no="Detaljinstruks / veiledning",
        description_no="Brukes for interne instrukser som operasjonaliserer regelverket.",
        from_doc_types=("INSTRUKS",),
        to_doc_types=("LOV", "FORSKRIFT", "ISA", "ISQM"),
        relation_type="GUIDANCE_FOR",
        default_note="Detaljinstruks/veiledning for praktisk gjennomføring.",
        allow_reverse=True,
    ),
    RelationTemplate(
        key="ISA_GJELDER_FOR_LOV",
        label_no="Standard relevant for lov/forskrift",
        description_no="Brukes for å koble ISA/ISQM til relevant lov/forskrift (doc-level eller anker-nivå).",
        from_doc_types=("ISA", "ISQM"),
        to_doc_types=("LOV", "FORSKRIFT"),
        relation_type="APPLIES_TO",
        default_note="Standarden er relevant for etterlevelse av regelverket.",
        allow_reverse=True,
    ),
]


def all_templates() -> List[RelationTemplate]:
    return list(_TEMPLATES)


def templates_for_pair(from_doc_type: str, to_doc_type: str) -> List[ApplicableTemplate]:
    """Returnerer relasjonsmaler som passer for doc_type-par.

    Dersom malen matcher i 'reverse' betyr det at malen anbefaler å bytte Fra/Til.
    """
    out: List[ApplicableTemplate] = []
    for t in _TEMPLATES:
        direction = t.match_direction(from_doc_type, to_doc_type)
        if direction:
            out.append(ApplicableTemplate(template=t, direction=direction))
    return out


def describe_applicable_template(app: ApplicableTemplate) -> str:
    t = app.template
    dir_txt = "" if app.direction == "forward" else " (anbefaler å bytte Fra/Til)"
    rt = relation_type_label(t.relation_type)
    return f"{t.label_no}{dir_txt} – {rt} ({t.relation_type})"
