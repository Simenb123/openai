from __future__ import annotations

"""rag_assistant.relation_io

Import/eksport av relasjoner (CSV/JSON).

Hvorfor?
--------
Relasjonskartet blir fort et "produkt" i seg selv:
- du vil kunne masseredigere, versjonere, dele og gjenbruke relasjoner
- du vil kunne starte i GUI, men ha mulighet til å gjøre endringer i Excel/VSCode

CSV-format (standard)
---------------------
Vi bruker semikolon (;) som standard delimiter ved eksport, fordi dette ofte
fungerer bedre med norsk Excel (komma brukes som desimaltegn).

Kolonner:
- from_id
- from_anchor
- relation_type
- to_id
- to_anchor
- note

Import er robust:
- støtter ; og , som delimiter
- støtter noen vanlige norske/engelske kolonnenavn-varianter
- tolererer at note mangler

JSON-format
-----------
Eksport: liste av dicts med samme feltnavn.
Import: støtter både:
  - en liste direkte
  - et objekt med nøkkel "relations" som inneholder listen
"""

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .kildebibliotek import Relation


@dataclass(frozen=True)
class RelationImportResult:
    relations: List[Relation]
    warnings: List[str]


_CANON = ("from_id", "from_anchor", "relation_type", "to_id", "to_anchor", "note")


def _norm_col(name: str) -> str:
    s = (name or "").strip().lower()
    s = s.replace(" ", "_").replace("-", "_")
    return s


def _map_columns(fieldnames: Sequence[str]) -> Dict[str, str]:
    """Mapper input-kolonnenavn til canonical feltnavn."""
    mapping: Dict[str, str] = {}

    # Synonymer
    syn = {
        "from_id": {"from_id", "from", "fra", "fra_id", "fromid", "fraid", "kilde_fra", "source_from"},
        "to_id": {"to_id", "to", "til", "til_id", "toid", "tilid", "kilde_til", "source_to"},
        "from_anchor": {"from_anchor", "fra_anker", "fromanchor", "fraanker", "anker_fra", "anchor_from"},
        "to_anchor": {"to_anchor", "til_anker", "toanchor", "tilanker", "anker_til", "anchor_to"},
        "relation_type": {"relation_type", "type", "rel_type", "relasjonstype", "relasjon_type"},
        "note": {"note", "notat", "comment", "kommentar", "beskrivelse", "description"},
    }

    for raw in fieldnames:
        n = _norm_col(raw)
        for canon, names in syn.items():
            if n in names and canon not in mapping:
                mapping[canon] = raw
                break

    return mapping


def _guess_delimiter(sample: str) -> str:
    # Prøv csv.Sniffer først
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t,")
        if dialect.delimiter in (";", ",", "\t"):
            return dialect.delimiter
    except Exception:
        pass

    # Enkel heuristikk
    if sample.count(";") > sample.count(","):
        return ";"
    return ","


def export_relations_to_csv(relations: Iterable[Relation], path: str | Path, *, delimiter: str = ";") -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    rows = list(relations)
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=delimiter)
        w.writerow(list(_CANON))
        for r in rows:
            w.writerow(
                [
                    r.from_id,
                    r.from_anchor or "",
                    r.relation_type,
                    r.to_id,
                    r.to_anchor or "",
                    r.note or "",
                ]
            )
    return len(rows)


def export_relations_to_json(relations: Iterable[Relation], path: str | Path) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    rows = list(relations)
    data = []
    for r in rows:
        data.append(
            {
                "from_id": r.from_id,
                "from_anchor": r.from_anchor,
                "relation_type": r.relation_type,
                "to_id": r.to_id,
                "to_anchor": r.to_anchor,
                "note": r.note,
            }
        )

    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(rows)


def import_relations_from_csv(path: str | Path) -> RelationImportResult:
    p = Path(path)
    warnings: List[str] = []
    if not p.exists():
        return RelationImportResult([], [f"Finner ikke fil: {p}"])

    sample = p.read_text(encoding="utf-8-sig", errors="replace")[:4096]
    delim = _guess_delimiter(sample)

    relations: List[Relation] = []

    with p.open("r", encoding="utf-8-sig", newline="") as f:
        # Prøv DictReader (header)
        reader = csv.reader(f, delimiter=delim)
        try:
            first_row = next(reader)
        except StopIteration:
            return RelationImportResult([], ["Tom fil"])

        # reset file pointer
        f.seek(0)

        header_like = False
        try:
            m0 = _map_columns(first_row)
            header_like = ("from_id" in m0) or ("to_id" in m0) or ("relation_type" in m0)
        except Exception:
            header_like = False
        if header_like:
            dr = csv.DictReader(f, delimiter=delim)
            fieldnames = dr.fieldnames or []
            mapping = _map_columns(fieldnames)

            # minimum: from_id + to_id
            if "from_id" not in mapping or "to_id" not in mapping:
                warnings.append(
                    "CSV-header mangler obligatoriske kolonner. Forventet minst from_id og to_id."
                )

            for i, row in enumerate(dr, start=2):
                try:
                    rel = _relation_from_row(row, mapping)
                    if rel is None:
                        warnings.append(f"Hopper over linje {i}: mangler from_id/to_id")
                        continue
                    relations.append(rel)
                except Exception as e:
                    warnings.append(f"Hopper over linje {i}: {e}")
        else:
            # fallback: posisjonell
            pr = csv.reader(f, delimiter=delim)
            for i, row in enumerate(pr, start=1):
                if not row or all((c or "").strip() == "" for c in row):
                    continue
                # forvent rekkefølge: from_id, from_anchor, relation_type, to_id, to_anchor, note
                while len(row) < 6:
                    row.append("")
                try:
                    from_id = (row[0] or "").strip()
                    to_id = (row[3] or "").strip()
                    if not from_id or not to_id:
                        warnings.append(f"Hopper over linje {i}: mangler from_id/to_id")
                        continue
                    relations.append(
                        Relation(
                            from_id=from_id,
                            from_anchor=(row[1] or "").strip() or None,
                            relation_type=(row[2] or "RELATES_TO").strip() or "RELATES_TO",
                            to_id=to_id,
                            to_anchor=(row[4] or "").strip() or None,
                            note=(row[5] or "").strip() or None,
                        )
                    )
                except Exception as e:
                    warnings.append(f"Hopper over linje {i}: {e}")

    return RelationImportResult(relations, warnings)


def _relation_from_row(row: Dict[str, Any], mapping: Dict[str, str]) -> Optional[Relation]:
    def g(canon: str) -> str:
        col = mapping.get(canon)
        if not col:
            return ""
        v = row.get(col)
        return "" if v is None else str(v)

    from_id = g("from_id").strip()
    to_id = g("to_id").strip()
    if not from_id or not to_id:
        return None

    return Relation(
        from_id=from_id,
        to_id=to_id,
        relation_type=g("relation_type").strip() or "RELATES_TO",
        from_anchor=g("from_anchor").strip() or None,
        to_anchor=g("to_anchor").strip() or None,
        note=g("note").strip() or None,
    )


def import_relations_from_json(path: str | Path) -> RelationImportResult:
    p = Path(path)
    warnings: List[str] = []
    if not p.exists():
        return RelationImportResult([], [f"Finner ikke fil: {p}"])

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return RelationImportResult([], [f"Kunne ikke lese JSON: {e}"])

    if isinstance(data, dict) and "relations" in data:
        data = data.get("relations")

    if not isinstance(data, list):
        return RelationImportResult([], ["JSON må være en liste eller et objekt med 'relations'"])

    rels: List[Relation] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            warnings.append(f"Hopper over element {idx}: ikke et objekt")
            continue

        # støtt synonymer i JSON også
        norm = {_norm_col(k): v for k, v in item.items()}
        from_id = str(norm.get("from_id") or norm.get("from") or norm.get("fra") or "").strip()
        to_id = str(norm.get("to_id") or norm.get("to") or norm.get("til") or "").strip()
        if not from_id or not to_id:
            warnings.append(f"Hopper over element {idx}: mangler from_id/to_id")
            continue

        rel_type = str(
            norm.get("relation_type") or norm.get("type") or norm.get("relasjonstype") or "RELATES_TO"
        ).strip() or "RELATES_TO"

        from_anchor = str(norm.get("from_anchor") or norm.get("fra_anker") or "").strip() or None
        to_anchor = str(norm.get("to_anchor") or norm.get("til_anker") or "").strip() or None
        note = str(norm.get("note") or norm.get("notat") or "").strip() or None

        try:
            rels.append(
                Relation(
                    from_id=from_id,
                    to_id=to_id,
                    relation_type=rel_type,
                    from_anchor=from_anchor,
                    to_anchor=to_anchor,
                    note=note,
                )
            )
        except Exception as e:
            warnings.append(f"Hopper over element {idx}: {e}")

    return RelationImportResult(rels, warnings)
