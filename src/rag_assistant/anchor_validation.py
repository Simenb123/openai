from __future__ import annotations

"""rag_assistant.anchor_validation

Hjelpe-modul for å validere ankere mot anker-inventory (kildebibliotek.anchors.json).

Brukes primært i GUI:
- Når bruker lager relasjon på paragraf/punkt-nivå (from_anchor/to_anchor), ønsker vi å
  advare hvis ankeret ikke finnes i ankerlisten for valgt kilde.

Viktig:
- Dette er kun "validering med advarsel". Vi blokkerer ikke lagring permanent,
  fordi brukeren kan ha legitime behov for manuelle ankere (f.eks. før reindeksering).
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .anchors import normalize_anchor


@dataclass(frozen=True)
class AnchorCheck:
    status: str
    """En av: ok | missing_inventory | empty_inventory | unknown_anchor"""

    source_id: str
    input_anchor: Optional[str]
    normalized_anchor: Optional[str]
    anchors_count: int
    suggestions: List[str]

    def is_ok(self) -> bool:
        return self.status == "ok"


def anchors_for_source(anchor_inventory: Dict[str, Any], source_id: str) -> List[str]:
    sid = (source_id or "").strip()
    if not sid:
        return []
    sources = (anchor_inventory or {}).get("sources")
    if not isinstance(sources, dict):
        return []
    entry = sources.get(sid) or {}
    anchors = entry.get("anchors") or []
    return [str(a) for a in anchors if str(a).strip()]


def _suggest_prefix(norm_anchor: str) -> str:
    """Velger et prefix for å gi meningsfulle forslag."""
    a = norm_anchor or ""

    if a.startswith("§"):
        # Eksempler:
        #  - §1-1 -> prefix §1-1
        #  - §1-1(3) -> prefix §1-1(
        #  - §1-1(1)[b] -> prefix §1-1(1)[
        if "[" in a:
            return a.split("[")[0] + "["
        if "(" in a:
            return a.split("(")[0] + "("
        # paragrafnivå
        m = re.match(r"^§(\d+)", a)
        return f"§{m.group(1)}" if m else "§"

    if a.startswith("P"):
        m = re.match(r"^(P\d{1,3})", a)
        return m.group(1) if m else "P"

    if a.startswith("A"):
        m = re.match(r"^(A\d{1,3})", a)
        return m.group(1) if m else "A"

    return a[:2]


def check_anchor(anchor_inventory: Dict[str, Any], source_id: str, anchor: Optional[str]) -> AnchorCheck:
    """Validerer ett anker mot inventory.

    Returnerer status:
      - ok: anchor er None/tom eller finnes i inventory
      - missing_inventory: inventory har ingen entry for source_id
      - empty_inventory: inventory har entry, men anchors er tom
      - unknown_anchor: anchors finnes, men anchor ble ikke funnet
    """
    sid = (source_id or "").strip()
    norm = normalize_anchor(anchor)

    if not norm:
        return AnchorCheck(
            status="ok",
            source_id=sid,
            input_anchor=anchor,
            normalized_anchor=None,
            anchors_count=0,
            suggestions=[],
        )

    sources = (anchor_inventory or {}).get("sources")
    if not isinstance(sources, dict) or sid not in sources:
        return AnchorCheck(
            status="missing_inventory",
            source_id=sid,
            input_anchor=anchor,
            normalized_anchor=norm,
            anchors_count=0,
            suggestions=[],
        )

    anchors = anchors_for_source(anchor_inventory, sid)
    if not anchors:
        return AnchorCheck(
            status="empty_inventory",
            source_id=sid,
            input_anchor=anchor,
            normalized_anchor=norm,
            anchors_count=0,
            suggestions=[],
        )

    inv_norm = {normalize_anchor(a) for a in anchors}
    if norm in inv_norm:
        return AnchorCheck(
            status="ok",
            source_id=sid,
            input_anchor=anchor,
            normalized_anchor=norm,
            anchors_count=len(anchors),
            suggestions=[],
        )

    prefix = _suggest_prefix(norm)
    suggestions = [a for a in anchors if str(a).startswith(prefix)][:10]
    return AnchorCheck(
        status="unknown_anchor",
        source_id=sid,
        input_anchor=anchor,
        normalized_anchor=norm,
        anchors_count=len(anchors),
        suggestions=suggestions,
    )
