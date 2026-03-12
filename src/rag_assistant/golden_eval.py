from __future__ import annotations

"""rag_assistant.golden_eval

Golden questions / retrieval-evaluering (D5).

Mål:
- Før man fyller på med 1000+ kilder, vil man ha en enkel måte å sjekke om retrieval
  faktisk treffer de riktige kildene/ankerene for et sett representative spørsmål.
- Dette er *ikke* en full LLM-kvalitetsevaluering, men en rask "retrieval sanity check".

Format (JSON):
[
  {
    "id": "isa230_p8",
    "question": "Hva sier ISA 230 punkt 8 om revisjonsdokumentasjon?",
    "expect": {
      "sources": ["ISA-230"],
      "anchors": [{"source_id": "ISA-230", "anchor": "P8"}]
    }
  }
]

Eval:
- Vi kjører make_context(question, collection, ...) og ser hvilke chunks som ble brukt.
- Treffer vi forventede sources/anchors? (best-effort med anker-hierarki)

Viktig:
- Dette modulen er skrevet slik at kjerne-logikken kan testes uten OpenAI/Chroma.
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .anchors import anchor_hierarchy, normalize_anchor
from .rag_bridge import ContextChunk, make_context
from .rag_bridge import QueryableCollection


@dataclass(frozen=True)
class ExpectedAnchor:
    source_id: str
    anchor: str


@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    question: str
    expected_sources: List[str]
    expected_anchors: List[ExpectedAnchor]


@dataclass(frozen=True)
class GoldenResult:
    case_id: str
    question: str
    expected_sources: List[str]
    expected_anchors: List[Dict[str, str]]

    retrieved_sources: List[str]
    retrieved_anchors: List[Dict[str, str]]

    hit_sources: List[str]
    hit_anchors: List[Dict[str, str]]

    pass_all: bool


def _now_iso_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_golden_cases(path: str | Path) -> List[GoldenCase]:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Golden file må være en JSON-liste")

    out: List[GoldenCase] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or "").strip()
        q = str(raw.get("question") or "").strip()
        expect = raw.get("expect") or {}
        exp_sources = [str(s).strip() for s in (expect.get("sources") or []) if str(s).strip()]
        exp_anchors_raw = expect.get("anchors") or []
        exp_anchors: List[ExpectedAnchor] = []
        if isinstance(exp_anchors_raw, list):
            for a in exp_anchors_raw:
                if not isinstance(a, dict):
                    continue
                sid = str(a.get("source_id") or "").strip()
                an = str(a.get("anchor") or "").strip()
                if sid and an:
                    exp_anchors.append(ExpectedAnchor(source_id=sid, anchor=an))
        if cid and q:
            out.append(GoldenCase(case_id=cid, question=q, expected_sources=exp_sources, expected_anchors=exp_anchors))
    return out


def _anchor_matches(expected: str, got: str) -> bool:
    e = normalize_anchor(expected) or expected
    g = normalize_anchor(got) or got
    if not e or not g:
        return False
    if e == g:
        return True
    # Hierarki-match: §1-1 matcher §1-1(1)[a], og P8 matcher P8.1 osv.
    if e in anchor_hierarchy(g):
        return True
    if g in anchor_hierarchy(e):
        return True
    return False


def evaluate_case_on_chunks(case: GoldenCase, used_chunks: Sequence[ContextChunk]) -> GoldenResult:
    retrieved_sources_set: set[str] = set()
    retrieved_anchor_pairs: List[Tuple[str, str]] = []

    for ch in used_chunks:
        meta = ch.metadata or {}
        sid = str(meta.get("source_id") or "").strip()
        if sid:
            retrieved_sources_set.add(sid)
        anchor = str(meta.get("anchor") or "").strip()
        if sid and anchor:
            retrieved_anchor_pairs.append((sid, anchor))

    retrieved_sources = sorted(retrieved_sources_set)

    # dedup anchors preserve order
    seen_pairs = set()
    retrieved_anchors: List[Dict[str, str]] = []
    for sid, anch in retrieved_anchor_pairs:
        key = (sid, anch)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        retrieved_anchors.append({"source_id": sid, "anchor": anch})

    # hits
    hit_sources = [s for s in case.expected_sources if s in retrieved_sources_set]

    hit_anchors: List[Dict[str, str]] = []
    for exp in case.expected_anchors:
        found = False
        for sid, anch in retrieved_anchor_pairs:
            if sid != exp.source_id:
                continue
            if _anchor_matches(exp.anchor, anch):
                found = True
                break
        if found:
            hit_anchors.append({"source_id": exp.source_id, "anchor": exp.anchor})

    pass_all = (len(hit_sources) == len(case.expected_sources)) and (len(hit_anchors) == len(case.expected_anchors))

    return GoldenResult(
        case_id=case.case_id,
        question=case.question,
        expected_sources=list(case.expected_sources),
        expected_anchors=[{"source_id": a.source_id, "anchor": a.anchor} for a in case.expected_anchors],
        retrieved_sources=retrieved_sources,
        retrieved_anchors=retrieved_anchors,
        hit_sources=hit_sources,
        hit_anchors=hit_anchors,
        pass_all=pass_all,
    )


def run_golden_eval(
    cases: Sequence[GoldenCase],
    *,
    collection: QueryableCollection,
    library_path: str | None = None,
    n_results: int = 5,
    expand_relations: bool = True,
) -> Dict[str, Any]:
    """Kjører eval for alle cases og returnerer en rapport-dict."""
    results: List[GoldenResult] = []
    for c in cases:
        _context, used = make_context(
            c.question,
            collection,
            n_results=max(1, int(n_results)),
            library_path=library_path,
            expand_relations=expand_relations,
        )
        results.append(evaluate_case_on_chunks(c, used))

    n_pass = sum(1 for r in results if r.pass_all)
    report = {
        "generated_at": _now_iso_z(),
        "cases": len(results),
        "passed": n_pass,
        "failed": len(results) - n_pass,
        "results": [r.__dict__ for r in results],
    }
    return report


def save_report(report: Dict[str, Any], path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
