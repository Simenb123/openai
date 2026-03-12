from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .anchors import normalize_anchor
from .document_ingestor import DocumentIngestor, ParsedDocument

logger = logging.getLogger(__name__)


# Lov-/forskrift-ankere: linjer som starter med "§ 1-1" osv.
LEGAL_ANCHOR_RE = re.compile(r"(?m)^(§\s*\d+(?:-\d+)*[a-zA-Z]?)\b")

# Ledd i lovtekst: linjer som starter med "(1)" osv.
LEGAL_LEDD_LINE_RE = re.compile(r"(?m)^\s*\(\s*(\d{1,2})\s*\)\s*")

# Bokstavpunkter i lovtekst: linjer som starter med "a)" / "a." (med mulig innrykk)
LEGAL_BOKSTAV_LINE_RE = re.compile(r"(?m)^\s*([a-z])\s*[\)\.]\s+")

# Standard-ankere (ISA/ISQM osv.)
# - Hovedavsnitt/punkt: "8." / "8)" / "1.2." osv. -> lagres som P8 / P1.2
PARA_ANCHOR_RE = re.compile(r"(?m)^(\d{1,3}(?:\.\d+)*)\s*[\.)]\s+")
# - Application material: "A1" / "A1." osv. -> lagres som A1
APP_ANCHOR_RE = re.compile(r"(?m)^(A\d{1,3})\s*(?:[\.)])?\s+")


def chunk_text(text: str, *, chunk_size: int = 1200, chunk_overlap: int = 200) -> List[str]:
    """Splitter tekst i overlappende chunks (tegnbasert).

    - chunk_overlap må være < chunk_size
    - Returnerer alltid chunks med minst 1 tegn (etter strip)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size må være > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap må være >= 0 og < chunk_size")

    t = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return []

    if len(t) <= chunk_size:
        return [t]

    out: List[str] = []
    start = 0
    while start < len(t):
        end = min(len(t), start + chunk_size)
        chunk = t[start:end].strip()
        if chunk:
            out.append(chunk)
        if end >= len(t):
            break
        start = max(0, end - chunk_overlap)
    return out


def _split_bokstav_sections(
    *,
    par_anchor: str,
    header_line: str,
    text_block: str,
    ledd_num: Optional[int],
) -> List[Tuple[str, str]]:
    matches = list(LEGAL_BOKSTAV_LINE_RE.finditer(text_block))
    if not matches:
        return []

    out: List[Tuple[str, str]] = []

    # Hvis vi er inne i et ledd, ta med første linje i ledd-blokken som kontekst.
    ledd_intro: Optional[str] = None
    if ledd_num is not None:
        lines = [ln for ln in text_block.splitlines() if ln.strip()]
        ledd_intro = lines[0].strip() if lines else None

    positions = [(m.start(), (m.group(1) or "").lower()) for m in matches]
    positions.append((len(text_block), ""))

    for (start, letter), (end, _next_letter) in zip(positions, positions[1:]):
        block = text_block[start:end].strip()
        if not block:
            continue

        anchor = par_anchor
        if ledd_num is not None:
            anchor += f"({ledd_num})"
        anchor += f"[{letter}]"
        anchor = normalize_anchor(anchor) or anchor

        parts = [header_line]
        if ledd_intro:
            parts.append(ledd_intro)
        parts.append(block)
        out.append((anchor, "\n".join(parts).strip()))

    return out


def _split_legal_subsections(par_anchor: str, par_text: str) -> List[Tuple[str, str]]:
    """Lager ekstra seksjoner for ledd/bokstav i en paragraf.

    Returnerer liste av (anchor, section_text). Disse seksjonene kommer i tillegg til paragraf-seksjonen.

    Strategi:
      - Paragraf-seksjonen ("§1-1") indekseres som før (hele paragrafen).
      - Hvis paragrafen inneholder ledd-markører på linjestart, lager vi seksjoner per ledd:
          "§1-1(1)", "§1-1(2)" ...
      - Hvis ledd/paragraph inneholder bokstavpunkter på linjestart, lager vi seksjoner per bokstav:
          "§1-1(1)[a]", ...

    Dette gir bedre presisjon ved relasjonsbygging og ved anker-ekspansjon.
    """
    t = (par_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = t.splitlines()
    if not lines:
        return []

    header_line = lines[0].strip()
    rest = "\n".join(lines[1:]).strip("\n")
    if not rest.strip():
        return []

    out: List[Tuple[str, str]] = []

    ledd_matches = list(LEGAL_LEDD_LINE_RE.finditer(rest))
    if ledd_matches:
        positions = [(m.start(), int(m.group(1))) for m in ledd_matches]
        positions.append((len(rest), -1))

        for (start, ledd_num), (end, _next_num) in zip(positions, positions[1:]):
            block = rest[start:end].strip()
            if not block:
                continue

            anchor = normalize_anchor(f"{par_anchor}({ledd_num})") or f"{par_anchor}({ledd_num})"
            out.append((anchor, f"{header_line}\n{block}".strip()))

            # Bokstavpunkter inne i ledd
            out.extend(
                _split_bokstav_sections(
                    par_anchor=par_anchor,
                    header_line=header_line,
                    text_block=block,
                    ledd_num=ledd_num,
                )
            )

        return out

    # Ingen ledd-markører: sjekk bokstavpunkter direkte i paragraf-body
    out.extend(
        _split_bokstav_sections(
            par_anchor=par_anchor,
            header_line=header_line,
            text_block=rest,
            ledd_num=None,
        )
    )
    return out


def split_anchored_sections(text: str) -> List[Tuple[Optional[str], str]]:
    """Forsøker å splitte tekst i logiske seksjoner med ankere.

    Prioritet:
    1) Lov-/forskrift-ankere: linjer som starter med "§ 1-1" etc.
       - I tillegg lager vi seksjoner per ledd/bokstav når det finnes.
    2) Standard-ankere: linjer som starter med "1." / "1)" osv. (P...) og "A1" (A...).

    Returnerer liste av (anchor, section_text).
    Hvis ingen ankere finnes: [(None, full_text)].
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")

    # --- Juridisk ---
    matches = list(LEGAL_ANCHOR_RE.finditer(t))
    if matches:
        out: List[Tuple[Optional[str], str]] = []

        positions = [(m.start(), normalize_anchor(m.group(1)) or None) for m in matches]

        # Preface før første paragraf
        first_start = positions[0][0]
        pre = t[:first_start].strip()
        if pre:
            out.append((None, pre))

        positions.append((len(t), None))

        for (start, par_anchor), (end, _next_anchor) in zip(positions, positions[1:]):
            section = t[start:end].strip()
            if not section:
                continue

            out.append((par_anchor, section))

            # Bygg ledd/bokstav underseksjoner
            if par_anchor:
                out.extend(_split_legal_subsections(par_anchor, section))

        return out

    # --- Standarder (ISA/ISQM) ---

    # Kombiner P- og A-ankere (så ISA-dokument kan inneholde begge)
    positions2: List[Tuple[int, Optional[str]]] = []

    for m in APP_ANCHOR_RE.finditer(t):
        a = normalize_anchor(m.group(1))
        if a:
            positions2.append((m.start(), a.upper()))

    for m in PARA_ANCHOR_RE.finditer(t):
        raw = m.group(1)
        a = normalize_anchor(f"P{raw}")
        if a:
            positions2.append((m.start(), a))

    if positions2:
        positions2.sort(key=lambda x: x[0])
        out: List[Tuple[Optional[str], str]] = []

        # Preface før første anker
        first_start = positions2[0][0]
        pre = t[:first_start].strip()
        if pre:
            out.append((None, pre))

        positions3 = list(positions2)
        positions3.append((len(t), None))
        for (start, anchor), (end, _next) in zip(positions3, positions3[1:]):
            section = t[start:end].strip()
            if section:
                out.append((anchor, section))
        return out

    return [(None, t.strip())] if t.strip() else []


def ingest_files(
    path: str | Path,
    *,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
    base_metadata: Optional[Dict[str, Any]] = None,
    recursive: bool = True,
) -> List[Dict[str, Any]]:
    """Ingest file eller mappe til en liste med chunks.

    Returnerer liste med dict:
      {"text": "...", "metadata": {...}}

    Best-effort:
    - Ved mappe: hopper over ikke-støttede filer (logges)
    - Ved enkeltfil: kaster ValueError for ikke-støttet filtype
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Finner ikke: {p}")

    ingestor = DocumentIngestor()
    docs: List[ParsedDocument] = []

    if p.is_file():
        docs = [ingestor.parse_file(p)]
    else:
        files: Iterable[Path]
        if recursive:
            files = (x for x in p.rglob("*") if x.is_file())
        else:
            files = (x for x in p.iterdir() if x.is_file())

        for f in sorted(files):
            try:
                docs.append(ingestor.parse_file(f))
            except ValueError as e:
                logger.warning("Hopper over fil (ikke støttet): %s (%s)", f, e)
            except Exception as e:
                logger.warning("Hopper over fil (ukjent feil): %s (%s)", f, e)

    out: List[Dict[str, Any]] = []
    for doc in docs:
        meta_base: Dict[str, Any] = {}
        meta_base.update(doc.metadata)
        if base_metadata:
            meta_base.update(base_metadata)

        sections = split_anchored_sections(doc.text)
        if not sections:
            continue

        generated: List[Dict[str, Any]] = []
        global_i = 0

        for section_idx, (anchor, section_text) in enumerate(sections):
            chunks = chunk_text(section_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            if not chunks:
                continue
            for local_i, chunk in enumerate(chunks):
                meta = dict(meta_base)
                meta["chunk_index"] = global_i  # global per fil
                meta["section_index"] = section_idx
                meta["section_chunk_index"] = local_i
                if anchor:
                    meta["anchor"] = anchor
                else:
                    # fallback: prøv å finne første anker i chunk
                    m = LEGAL_ANCHOR_RE.search(chunk)
                    if m:
                        meta["anchor"] = normalize_anchor(m.group(1))
                    else:
                        m2 = APP_ANCHOR_RE.search(chunk)
                        if m2:
                            meta["anchor"] = (normalize_anchor(m2.group(1)) or "").upper() or None
                        else:
                            m3 = PARA_ANCHOR_RE.search(chunk)
                            if m3:
                                meta["anchor"] = normalize_anchor(f"P{m3.group(1)}")
                generated.append({"text": chunk, "metadata": meta})
                global_i += 1

        # chunk_total settes per fil
        for item in generated:
            item["metadata"]["chunk_total"] = global_i

        out.extend(generated)

    return out
