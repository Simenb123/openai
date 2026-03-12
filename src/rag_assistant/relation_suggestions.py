from __future__ import annotations

"""rag_assistant.relation_suggestions

Relasjonstyper + forslag for relasjonsbygging.

Bakgrunn
--------
I et revisjons-RAG vil vi ofte koble:
  - revisjonsstandarder (ISA/ISQM)
  - lov/forskrift
  - forarbeider
  - dommer
  - Finanstilsynets tilsynsrapporter
  - fagartikler, lovkommentarer og interne instrukser

For at relasjonsbygging skal være lett i GUI, tilbyr vi:
  - Et definert sett relasjonstyper med norsk label + kort forklaring
  - Forslag til relasjonstyper basert på doc_type (Fra/Til)
  - Hint om "vanlig" retning når brukeren har valgt en utypisk Fra/Til

Relasjonstype-keys lagres i `kildebibliotek.json` (som før), så vi holder
relasjonstype-strengene stabile og maskinvennlige.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


def _norm_doc_type(v: Optional[str]) -> str:
    s = (v or "").strip().upper()
    return s or "OTHER"


@dataclass(frozen=True)
class RelationTypeDef:
    key: str
    label_no: str
    description_no: str
    directional: bool = True


# NB: keys bør være stabile over tid (de skrives til JSON).
RELATION_TYPE_DEFS: Dict[str, RelationTypeDef] = {
    "RELATES_TO": RelationTypeDef(
        key="RELATES_TO",
        label_no="Relaterer til",
        description_no="Generisk kobling (bruk når du ikke er sikker på eksakt type).",
        directional=False,
    ),
    "REFERS_TO": RelationTypeDef(
        key="REFERS_TO",
        label_no="Henviser til",
        description_no="Kilden henviser eksplisitt til den andre (f.eks. fotnote, paragrafhenvisning).",
        directional=True,
    ),
    "APPLIES_TO": RelationTypeDef(
        key="APPLIES_TO",
        label_no="Gjelder for",
        description_no="Standard/regelverk er relevant for, eller gjelder i lys av, den andre kilden.",
        directional=True,
    ),
    "CLARIFIES": RelationTypeDef(
        key="CLARIFIES",
        label_no="Presiserer",
        description_no="Kilden presiserer/utfyller innholdet i den andre.",
        directional=True,
    ),
    "AUTHORIZED_BY": RelationTypeDef(
        key="AUTHORIZED_BY",
        label_no="Hjemlet i",
        description_no="Forskrift/regel er gitt med hjemmel i den andre kilden (typisk lov).",
        directional=True,
    ),
    "INTERPRETS": RelationTypeDef(
        key="INTERPRETS",
        label_no="Tolkning / praksis",
        description_no="Kilden tolker, anvender eller illustrerer hvordan den andre forstås i praksis (dom/tilsyn).",
        directional=True,
    ),
    "COMMENTARY_ON": RelationTypeDef(
        key="COMMENTARY_ON",
        label_no="Kommentar til",
        description_no="Kilden er kommentar/veiledning til den andre (lovkommentar, fagartikkel, intern veiledning).",
        directional=True,
    ),
    "SUPERVISION_OF": RelationTypeDef(
        key="SUPERVISION_OF",
        label_no="Tilsyn av",
        description_no="Kilden er tilsyn/rapport som gjelder vurdering av etterlevelse av den andre.",
        directional=True,
    ),
    "PREPARATORY_WORKS_FOR": RelationTypeDef(
        key="PREPARATORY_WORKS_FOR",
        label_no="Forarbeid til",
        description_no="Kilden er forarbeid til den andre (lovforarbeider -> lov).",
        directional=True,
    ),
    "GUIDANCE_FOR": RelationTypeDef(
        key="GUIDANCE_FOR",
        label_no="Instruks / veiledning for",
        description_no="Kilden er en detaljinstruks/veiledning for praktisk bruk av den andre.",
        directional=True,
    ),
    # Legacy keys (beholdes for bakoverkompat)
    "IMPLEMENTS": RelationTypeDef(
        key="IMPLEMENTS",
        label_no="Implementerer",
        description_no="Kilden implementerer/operasjonaliserer den andre.",
        directional=True,
    ),
    "AMENDS": RelationTypeDef(
        key="AMENDS",
        label_no="Endrer",
        description_no="Kilden endrer eller opphever deler av den andre.",
        directional=True,
    ),
}


def all_relation_type_keys() -> List[str]:
    """Alle relasjonstype-keys (stabile)."""
    return list(RELATION_TYPE_DEFS.keys())


def relation_type_label(key: str) -> str:
    k = (key or "").strip()
    d = RELATION_TYPE_DEFS.get(k)
    return d.label_no if d else k


def relation_type_description(key: str) -> str:
    k = (key or "").strip()
    d = RELATION_TYPE_DEFS.get(k)
    return d.description_no if d else ""


def _dedup_keep_order(items: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for x in items:
        x2 = (x or "").strip()
        if not x2:
            continue
        if x2 in seen:
            continue
        if x2 not in RELATION_TYPE_DEFS:
            continue
        seen.add(x2)
        out.append(x2)
    return out


def suggest_relation_types(from_doc_type: str, to_doc_type: str) -> List[str]:
    """Forslag til relasjonstyper gitt doc_type for Fra/Til.

    Returnerer liste av relasjonstype-keys i anbefalt rekkefølge.
    Listen inkluderer alltid RELATES_TO som siste fallback.
    """
    f = _norm_doc_type(from_doc_type)
    t = _norm_doc_type(to_doc_type)

    # Standard fallback
    base = ["REFERS_TO", "APPLIES_TO", "CLARIFIES", "RELATES_TO"]

    if f == "FORSKRIFT" and t == "LOV":
        return _dedup_keep_order(["AUTHORIZED_BY", "CLARIFIES", "REFERS_TO", "RELATES_TO"])

    if f == "LOV" and t == "FORSKRIFT":
        # Retningen er ofte motsatt i praksis (se direction_hint).
        return _dedup_keep_order(["RELATES_TO", "REFERS_TO", "CLARIFIES", "AUTHORIZED_BY"])

    if f in {"ISA", "ISQM"} and t in {"LOV", "FORSKRIFT"}:
        return _dedup_keep_order(["APPLIES_TO", "REFERS_TO", "RELATES_TO"])

    if f in {"LOV", "FORSKRIFT"} and t in {"ISA", "ISQM"}:
        return _dedup_keep_order(["APPLIES_TO", "RELATES_TO", "REFERS_TO"])

    if f == "DOM" and t in {"LOV", "FORSKRIFT"}:
        return _dedup_keep_order(["INTERPRETS", "APPLIES_TO", "REFERS_TO", "RELATES_TO"])

    if f == "TILSYN" and t in {"LOV", "FORSKRIFT", "ISA", "ISQM"}:
        return _dedup_keep_order(["SUPERVISION_OF", "INTERPRETS", "RELATES_TO", "REFERS_TO"])

    if f == "FORARBEID" and t == "LOV":
        return _dedup_keep_order(["PREPARATORY_WORKS_FOR", "CLARIFIES", "REFERS_TO", "RELATES_TO"])

    if f in {"KOMMENTAR", "ARTIKKEL"} and t in {"LOV", "FORSKRIFT", "ISA", "ISQM"}:
        return _dedup_keep_order(["COMMENTARY_ON", "CLARIFIES", "REFERS_TO", "RELATES_TO"])

    if f == "INSTRUKS" and t in {"LOV", "FORSKRIFT", "ISA", "ISQM"}:
        return _dedup_keep_order(["GUIDANCE_FOR", "CLARIFIES", "REFERS_TO", "RELATES_TO"])

    if f == t:
        return _dedup_keep_order(["RELATES_TO", "REFERS_TO", "CLARIFIES"])

    return _dedup_keep_order(base)


def direction_hint(from_doc_type: str, to_doc_type: str) -> Optional[str]:
    """Gir et lite hint hvis Fra/Til ser ut til å være 'motsatt' vanlig praksis."""
    f = _norm_doc_type(from_doc_type)
    t = _norm_doc_type(to_doc_type)

    # Forskrift -> Lov er vanlig for "Hjemlet i" og "Presiserer"
    if f == "LOV" and t == "FORSKRIFT":
        return (
            "Tips: Ofte er det forskriften som er 'Fra' og loven som er 'Til' (Hjemlet i / Presiserer). "
            "Bruk 'Bytt Fra/Til' hvis det er det du mener."
        )

    # Dom -> lov/forskrift er vanlig for tolkning/praksis
    if f in {"LOV", "FORSKRIFT"} and t == "DOM":
        return "Tips: Vanlig retning er DOM -> LOV/FORSKRIFT (Tolkning / praksis). Vurder å bytte Fra/Til."

    # Kommentar/Artikkel -> regelverk er vanlig
    if f in {"LOV", "FORSKRIFT", "ISA", "ISQM"} and t in {"KOMMENTAR", "ARTIKKEL"}:
        return "Tips: Vanlig retning er KOMMENTAR/ARTIKKEL -> regelverk (Kommentar til / Presiserer). Vurder å bytte Fra/Til."

    # Forarbeid -> lov
    if f == "LOV" and t == "FORARBEID":
        return "Tips: Vanlig retning er FORARBEID -> LOV (Forarbeid til). Vurder å bytte Fra/Til."

    return None
