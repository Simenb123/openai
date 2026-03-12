from __future__ import annotations

"""rag_assistant.anchors

Felles funksjoner for "ankere" i RAG-systemet.

Hvorfor egen modul?
- Flere steder i koden trenger normalisering/parsing av ankere.
- Vi ønsker å støtte mer detaljert juridisk referering (ledd/bokstav) på en konsistent måte.

Anchor-konvensjon (intern):

Juridiske kilder (lov/forskrift/dommer):
- Paragraf:           §1-1
- Ledd:               §1-1(1)
- Bokstav:            §1-1(1)[a]
- Bokstav uten ledd:  §1-1[a]

Standarder (ISA/ISQM osv.):
- Punkt/avsnitt:      P8, P1.2
- Application material: A1

Merk:
- Vi normaliserer input for å tolerere varianter som "§ 1-1 (1)" og "§1-1(1)a".
- For standarder normaliserer vi "8" -> "P8".
"""

import re
from typing import Optional, Tuple, List


# ---- Normalisering av juridiske ankere ----

_LEGAL_BASE_RE = re.compile(r"^§(\d+(?:-\d+)*[A-Za-z]?)", re.IGNORECASE)
_LEGAL_LEDD_RE = re.compile(r"^\((\d{1,2})\)")
_LEGAL_LEDD_RE_LOOSE = re.compile(r"^\((\d{1,2})\)?")
_LEGAL_BOKSTAV_BRACKET_RE = re.compile(r"^\[([A-Za-z])\]")


def _strip_trailing_punct_keep_brackets(s: str) -> str:
    """Stripper enkel tegnsetting på slutten.

    Viktig: vi stripper IKKE ']' eller ')', fordi de kan være del av gyldig anker.
    """
    while s and s[-1] in ".,;:":
        s = s[:-1]
    return s


def _normalize_legal_anchor(raw_no_ws: str) -> str:
    s = _strip_trailing_punct_keep_brackets(raw_no_ws)
    m = _LEGAL_BASE_RE.match(s)
    if not m:
        return s

    base = f"§{m.group(1)}"
    rest = s[m.end() :]

    ledd: Optional[int] = None
    bokstav: Optional[str] = None

    if rest.startswith("("):
        m_ledd = _LEGAL_LEDD_RE.match(rest) or _LEGAL_LEDD_RE_LOOSE.match(rest)
        if m_ledd:
            try:
                ledd = int(m_ledd.group(1))
            except ValueError:
                ledd = None
            rest = rest[m_ledd.end() :]

    if rest.startswith("["):
        m_b = _LEGAL_BOKSTAV_BRACKET_RE.match(rest)
        if m_b:
            bokstav = m_b.group(1).lower()
            rest = rest[m_b.end() :]
    else:
        # støtt "...a" eller "...a)" / "...a." som enkel input
        m_b2 = re.match(r"^([A-Za-z])[\)\.]?$", rest)
        if m_b2:
            bokstav = m_b2.group(1).lower()

    out = base
    if ledd is not None:
        out += f"({ledd})"
    if bokstav is not None:
        out += f"[{bokstav}]"
    return out


# ---- Normalisering av standard-ankere ----

_P_RE = re.compile(r"^[pP](\d{1,3}(?:\.\d+)*)$")
_A_RE = re.compile(r"^[aA](\d{1,3})$")
_NUM_ONLY_RE = re.compile(r"^(\d{1,3}(?:\.\d+)*)$")


def normalize_anchor(anchor: Optional[str]) -> Optional[str]:
    """Normaliserer anker til intern standard.

    Returnerer None hvis input er None/tom.

    Eksempler:
      - "§ 1-1" -> "§1-1"
      - "§1-1 (1)" -> "§1-1(1)"
      - "§1-1(1)a" -> "§1-1(1)[a]"
      - "p8" -> "P8"
      - "8" -> "P8"
    """
    if anchor is None:
        return None
    raw = str(anchor).strip()
    if not raw:
        return None

    # Fjern all whitespace inne i strengen
    s = re.sub(r"\s+", "", raw)

    if s.startswith("§"):
        return _normalize_legal_anchor(s)

    # For standard-ankere: her ønsker vi å tåle "8)" osv.
    s2 = s.rstrip(".,;:)")
    if not s2:
        return None

    m = _P_RE.match(s2)
    if m:
        return f"P{m.group(1)}"

    m = _A_RE.match(s2)
    if m:
        return f"A{m.group(1)}"

    m = _NUM_ONLY_RE.match(s2)
    if m:
        return f"P{m.group(1)}"

    return s2


# ---- Sortering ----

_LEGAL_PARSE_RE = re.compile(
    r"^§(?P<par>\d+(?:-\d+)*[A-Za-z]?)(?:\((?P<ledd>\d{1,2})\))?(?:\[(?P<bokstav>[a-z])\])?$",
    re.IGNORECASE,
)


def anchor_sort_key(anchor: str) -> Tuple:
    """Sorteringsnøkkel for ankere.

    - Juridisk: paragraf først, deretter ledd, deretter bokstav.
    - Standard: P før A, med numerisk sort.
    """
    a = normalize_anchor(anchor) or ""

    if a.startswith("§"):
        m = _LEGAL_PARSE_RE.match(a)
        if m:
            par = m.group("par")
            ledd_s = m.group("ledd")
            bokstav = (m.group("bokstav") or "").lower()

            # Paragrafdelen: §1-1A -> [(1,""),(1,"A")]
            parts = par.split("-")
            parsed: List[Tuple[int, str]] = []
            for part in parts:
                m2 = re.fullmatch(r"(\d+)([A-Za-z]?)", part)
                if m2:
                    parsed.append((int(m2.group(1)), (m2.group(2) or "").upper()))
                else:
                    parsed.append((10**9, part.upper()))

            ledd = int(ledd_s) if ledd_s and ledd_s.isdigit() else 0
            return (0, parsed, ledd, bokstav)

        # fallback
        return (0, a)

    if a.startswith("P"):
        body = a[1:]
        nums: List[int] = []
        for x in body.split("."):
            try:
                nums.append(int(x))
            except ValueError:
                nums.append(10**9)
        return (1, nums)

    if a.startswith("A"):
        try:
            return (2, int(a[1:]))
        except ValueError:
            return (2, 10**9)

    return (3, a)


# ---- Hierarki / foreldreakkere (fallback) ----


def anchor_hierarchy(anchor: Optional[str]) -> List[str]:
    """Returnerer anker-hierarki fra mest spesifikk til mer generell.

    Brukes til "fallback" i relasjonsmatching og retrieval.

    Juridisk:
      - §1-1(1)[a] -> [§1-1(1)[a], §1-1(1), §1-1]
      - §1-1(1)    -> [§1-1(1), §1-1]
      - §1-1[a]    -> [§1-1[a], §1-1]
      - §1-1       -> [§1-1]

    Standarder:
      - P1.2 -> [P1.2, P1]
      - P8   -> [P8]
      - A1   -> [A1]
    """
    norm = normalize_anchor(anchor)
    if not norm:
        return []

    out: List[str] = []

    if norm.startswith("§"):
        m = _LEGAL_PARSE_RE.match(norm)
        if not m:
            return [norm]

        par = m.group("par")
        ledd = m.group("ledd")
        bokstav = m.group("bokstav")

        # mest spesifikk
        out.append(norm)

        # dropp bokstav
        if bokstav:
            if ledd:
                out.append(f"§{par}({ledd})")
            else:
                out.append(f"§{par}")

        # dropp ledd
        if ledd:
            out.append(f"§{par}")

        # paragrafnivå
        if not out or out[-1] != f"§{par}":
            out.append(f"§{par}")

        # dedup, behold rekkefølge
        seen = set()
        dedup: List[str] = []
        for a in out:
            a2 = normalize_anchor(a) or a
            if a2 in seen:
                continue
            seen.add(a2)
            dedup.append(a2)
        return dedup

    if norm.startswith("P"):
        out.append(norm)
        body = norm[1:]
        if "." in body:
            # P1.2.3 -> P1.2 -> P1
            parts = body.split(".")
            for i in range(len(parts) - 1, 0, -1):
                parent = "P" + ".".join(parts[:i])
                out.append(parent)
        # dedup
        seen = set()
        dedup = []
        for a in out:
            if a in seen:
                continue
            seen.add(a)
            dedup.append(a)
        return dedup

    # A-ankere og alt annet: ingen hierarki
    return [norm]


# ---- Ekstraksjon fra spørsmål (juridisk) ----

_LEGAL_REF_RE = re.compile(r"§\s*(\d+(?:-\d+)*[A-Za-z]?)", re.IGNORECASE)
_LEDD_PAREN_IN_TEXT_RE = re.compile(r"\(\s*(\d{1,2})\s*\)")
_LEDD_NUM_IN_TEXT_RE = re.compile(r"\b(\d{1,2})\s*\.?\s*ledd\b", re.IGNORECASE)
_BOKSTAV_IN_TEXT_RE = re.compile(r"\b(?:bokstav|litera)\s*([a-z])\b", re.IGNORECASE)
_BOKSTAV_BRACKET_IN_TEXT_RE = re.compile(r"\[\s*([A-Za-z])\s*\]")

_ORDINAL_MAP = {
    "første": 1,
    "andre": 2,
    "tredje": 3,
    "fjerde": 4,
    "femte": 5,
    "sjette": 6,
    "sjuende": 7,
    "syvende": 7,
    "åttende": 8,
    "niende": 9,
    "tiende": 10,
    "ellevte": 11,
    "tolvte": 12,
    "trettende": 13,
    "fjortende": 14,
    "femtende": 15,
    "sekstende": 16,
    "syttende": 17,
    "attende": 18,
    "nittende": 19,
    "tjuende": 20,
}

_LEDD_ORDINAL_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _ORDINAL_MAP.keys()) + r")\s+ledd\b",
    re.IGNORECASE,
)


def build_legal_anchor(paragraph: str, *, ledd: Optional[int] = None, bokstav: Optional[str] = None) -> str:
    """Bygger et juridisk anker i intern form."""
    base = normalize_anchor(f"§{paragraph}") or f"§{paragraph}"
    # normalize_anchor() vil fjerne whitespace og normalisere base.
    # Vi vil ikke at base skal inneholde ledd/bokstav her.
    # Derfor strip på eventuell '(' eller '['.
    base = base.split("(")[0].split("[")[0]

    out = base
    if ledd is not None:
        out += f"({int(ledd)})"
    if bokstav is not None:
        b = str(bokstav).strip().lower()
        if b:
            out += f"[{b[0]}]"
    return out


def extract_legal_anchor(text: str, *, tail_chars: int = 180) -> Optional[str]:
    """Ekstraher juridisk anker fra en bruker-tekst.

    Støtter:
      - "§ 1-1"
      - "§ 1-1 (1)"
      - "§ 1-1 første ledd"
      - "§ 1-1 (2) bokstav a"

    Returnerer normalisert intern anchor (f.eks. "§1-1(2)[a]") eller None.
    """
    if not text:
        return None

    m = _LEGAL_REF_RE.search(text)
    if not m:
        return None

    par = m.group(1)
    base = build_legal_anchor(par)

    tail = text[m.end() : m.end() + max(0, int(tail_chars))]

    ledd: Optional[int] = None
    bokstav: Optional[str] = None

    m_ledd = _LEDD_PAREN_IN_TEXT_RE.search(tail)
    if m_ledd:
        try:
            ledd = int(m_ledd.group(1))
        except ValueError:
            ledd = None
    else:
        m_ledd2 = _LEDD_NUM_IN_TEXT_RE.search(tail)
        if m_ledd2:
            try:
                ledd = int(m_ledd2.group(1))
            except ValueError:
                ledd = None
        else:
            m_ledd3 = _LEDD_ORDINAL_RE.search(tail)
            if m_ledd3:
                word = (m_ledd3.group(1) or "").lower()
                ledd = _ORDINAL_MAP.get(word)

    m_b = _BOKSTAV_IN_TEXT_RE.search(tail)
    if m_b:
        bokstav = (m_b.group(1) or "").lower()
    else:
        m_b2 = _BOKSTAV_BRACKET_IN_TEXT_RE.search(tail)
        if m_b2:
            bokstav = (m_b2.group(1) or "").lower()

    # Dersom vi fant bokstav men ikke ledd, lar vi det være ("§1-1[a]")
    return build_legal_anchor(par, ledd=ledd, bokstav=bokstav)
