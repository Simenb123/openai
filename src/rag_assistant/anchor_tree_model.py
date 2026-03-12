from __future__ import annotations

"""rag_assistant.anchor_tree_model

Pure (ikke-GUI) funksjoner for å bygge en hierarkisk tre-struktur av ankere.

Hvorfor:
- GUI trenger en trevisning for å navigere ankere på en effektiv måte
  (paragraf -> ledd -> bokstav, eller P1 -> P1.2 -> ...).
- For testing ønsker vi å holde logikken utenfor Tkinter.

Tre-modell:
- Vi representerer treet som en mapping: parent_anchor -> [child_anchor, ...]
  der parent_anchor kan være None for rot-noder.

- Barn sorteres med `anchors.anchor_sort_key`.

Filter:
- `filter_anchors_with_context` filtrerer ankere med substring-match, men inkluderer også
  foreldre-ankere slik at treet fortsatt gir kontekst.
"""

from typing import Dict, List, Optional, Sequence, Set

from .anchors import anchor_hierarchy, anchor_sort_key, normalize_anchor


def direct_parent(anchor: str) -> Optional[str]:
    """Returnerer direkte forelder-anker (ett nivå opp) eller None."""
    h = anchor_hierarchy(anchor)
    if len(h) >= 2:
        return h[1]
    return None


def complete_with_ancestors(anchors: Sequence[str]) -> List[str]:
    """Returnerer en dedupet liste av ankere + alle foreldre i hierarkiet."""
    seen: Set[str] = set()
    out: List[str] = []
    for a in anchors:
        na = normalize_anchor(a)
        if not na:
            continue
        for x in anchor_hierarchy(na) or [na]:
            nx = normalize_anchor(x) or x
            if nx in seen:
                continue
            seen.add(nx)
            out.append(nx)
    return out


def _normalize_query(q: str) -> str:
    return "".join((q or "").split()).upper()


def filter_anchors_with_context(
    anchors: Sequence[str],
    query: str,
    *,
    max_matches: int = 5000,
) -> List[str]:
    """Filtrer ankere med substring-match, og ta med foreldre for kontekst.

    - Matching skjer på normalisert form:
      - whitespace fjernes
      - upper()
    - Hvis query er tom, returneres alle ankere (inkl. foreldre).
    - max_matches begrenser antall *match* (foreldre kan komme i tillegg).
    """
    all_anchors = complete_with_ancestors(anchors)
    qn = _normalize_query(query)
    if not qn:
        return all_anchors

    matches: List[str] = []
    for a in all_anchors:
        an = _normalize_query(a)
        if qn in an:
            matches.append(a)
            if len(matches) >= max_matches:
                break

    # inkluder foreldre for hver match
    with_context: Set[str] = set()
    out: List[str] = []
    for m in matches:
        for x in anchor_hierarchy(m) or [m]:
            nx = normalize_anchor(x) or x
            if nx in with_context:
                continue
            with_context.add(nx)
            out.append(nx)

    return out


def build_tree_edges(anchors: Sequence[str]) -> Dict[Optional[str], List[str]]:
    """Bygger parent->children mapping for et sett ankere.

    Inkluderer automatisk foreldre i hierarkiet (slik at treet blir sammenhengende).
    """
    nodes = complete_with_ancestors(anchors)

    # parent for hver node
    parent_map: Dict[str, Optional[str]] = {}
    for a in nodes:
        parent_map[a] = direct_parent(a)

    children: Dict[Optional[str], Set[str]] = {}
    for node, parent in parent_map.items():
        children.setdefault(parent, set()).add(node)

    # noen noder kan ha en parent som ikke finnes i nodes (edge-case)
    # da flytter vi noden til rot (None).
    node_set = set(nodes)
    for parent, kids in list(children.items()):
        if parent is None:
            continue
        if parent not in node_set:
            # flytt til root
            for k in kids:
                children.setdefault(None, set()).add(k)
            children.pop(parent, None)

    # sortering
    sorted_children: Dict[Optional[str], List[str]] = {}
    for parent, kids in children.items():
        sorted_children[parent] = sorted(kids, key=anchor_sort_key)

    return sorted_children


def roots(edges: Dict[Optional[str], List[str]]) -> List[str]:
    """Henter rot-noder fra edges."""
    return list(edges.get(None, []))
