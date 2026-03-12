from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv


def find_project_root(start: Optional[Path] = None) -> Path:
    """Forsøker å finne prosjektroten.

    Heuristikk:
    - gå oppover fra `start` (eller cwd)
    - stopp når vi finner requirements.txt eller pyproject.toml
    - fallback: cwd
    """
    p = (start or Path.cwd()).resolve()
    for candidate in [p, *p.parents]:
        if (candidate / "requirements.txt").exists() or (candidate / "pyproject.toml").exists():
            return candidate
    return p


def load_env(env_path: Optional[Path] = None) -> Path:
    """Laster .env (hvis den finnes) og returnerer brukt path."""
    root = find_project_root()
    p = env_path or (root / ".env")
    if p.exists():
        load_dotenv(p)
    return p


def apply_env(settings: Any, *, override: bool = False) -> None:
    """Kompatibilitets-wrapper.

    `settings_profiles.apply_env()` brukes av build_index.
    Denne wrapperen gjør at admin_gui kan importere apply_env herfra.
    """
    try:
        from .settings_profiles import apply_env as _apply  # lokal import for å unngå sirkel

        _apply(settings, override=override)
    except Exception:
        # Vi ønsker ikke krasj i GUI hvis settings-modul er borte
        pass


def get_env_str(key: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(key)
    if v is None:
        return default
    v = v.strip()
    return v if v else default
