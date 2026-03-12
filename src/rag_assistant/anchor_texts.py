from __future__ import annotations

"""rag_assistant.anchor_texts

Hjelpefunksjoner for å hente tekst pr. anker, primært for GUI.

Hvorfor?
-----------
Når man bygger relasjoner på paragraf-/ledd-/bokstav-nivå trenger man ofte
en rask måte å se *innholdet* i ankeret man skal koble.

Denne modulen bygger en "anker -> tekst"-mapping ved å:
  - lese kildens filer (.txt/.pdf/.docx)
  - splitte dokumenttekst i ankere via `split_anchored_sections`

Designmål
---------
- Best-effort: hvis en fil feiler lesing, logges det og resten fortsetter
- Ikke avhengig av Chroma/indeks: fungerer før/uten indeksering
- Cachebar: GUI kan cache per source_id
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .anchors import normalize_anchor
from .document_ingestor import DocumentIngestor
from .file_ingest import split_anchored_sections
from .kildebibliotek import Library

logger = logging.getLogger(__name__)


def _resolve_file(base_dir: Path, file_path: str) -> Path:
    p = Path(file_path)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _append_limited(existing: str, addition: str, *, max_chars: int) -> str:
    if not addition:
        return existing
    if not existing:
        return addition[:max_chars]
    combined = existing + "\n\n" + addition
    return combined[:max_chars]


def build_anchor_text_map(
    library: Library,
    source_id: str,
    *,
    base_dir: str | Path,
    max_chars_per_anchor: int = 8000,
) -> Dict[str, str]:
    """Bygger mapping `anchor -> text` for én kilde.

    - Returnerer kun seksjoner med et identifisert anker (None-seksjoner ignoreres).
    - Tekst for samme anker kan forekomme flere ganger (flere filer). Vi appender
      med en enkel separator og begrenser lengden.
    """
    sid = (source_id or "").strip()
    if not sid:
        return {}

    src = library.get_source(sid)
    if not src:
        return {}

    base = Path(base_dir)
    ing = DocumentIngestor()
    out: Dict[str, str] = {}

    for fp in (src.files or []):
        try:
            p = _resolve_file(base, fp)
            doc = ing.parse_file(p)
        except Exception as e:
            logger.warning("Kunne ikke lese fil for anker-tekst (%s): %s", fp, e)
            continue

        sections = split_anchored_sections(doc.text)
        for anchor, section_text in sections:
            if not anchor:
                continue
            a = normalize_anchor(anchor) or anchor
            # Sett inn filnavn som topp-linje for kontekst når flere filer per kilde
            header = Path(fp).name
            text = f"[{header}]\n{section_text}" if header else section_text
            out[a] = _append_limited(out.get(a, ""), text.strip(), max_chars=max_chars_per_anchor)

    return out


def preview_text(text: str, *, max_len: int = 1600) -> str:
    """Gir en kort preview (for GUI)."""
    t = (text or "").strip()
    if not t:
        return ""
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


@dataclass
class AnchorTextCache:
    """En enkel cache for `anchor -> text` pr. source_id."""

    library: Library
    base_dir: Path
    max_chars_per_anchor: int = 8000

    _cache: Dict[str, Dict[str, str]] | None = None

    def _ensure(self) -> None:
        if self._cache is None:
            self._cache = {}

    def invalidate(self, source_id: Optional[str] = None) -> None:
        self._ensure()
        if source_id:
            self._cache.pop(source_id, None)
        else:
            self._cache.clear()

    def get(self, source_id: str) -> Dict[str, str]:
        sid = (source_id or "").strip()
        if not sid:
            return {}
        self._ensure()
        assert self._cache is not None
        if sid not in self._cache:
            self._cache[sid] = build_anchor_text_map(
                self.library,
                sid,
                base_dir=self.base_dir,
                max_chars_per_anchor=self.max_chars_per_anchor,
            )
        return self._cache[sid]
