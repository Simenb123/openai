from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def safe_json_loads(s: str) -> Dict[str, Any]:
    """Best-effort JSON->dict.

    - Returnerer {} ved tom/ugyldig JSON
    - Returnerer {} hvis JSON ikke er et objekt
    """
    s = (s or "").strip()
    if not s:
        return {}
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {}
    except Exception:
        return {}


def try_make_relative_path(file_path: str, *, root: Optional[Path] = None) -> str:
    """Forsøker å gjøre `file_path` relativ til `root` (default: cwd).

    Returnerer original path hvis relativisering feiler.
    """
    try:
        root_path = (root or Path.cwd()).resolve()
        p = Path(file_path).resolve()
        rel = p.relative_to(root_path)
        return str(rel).replace("\\", "/")
    except Exception:
        return str(file_path)
