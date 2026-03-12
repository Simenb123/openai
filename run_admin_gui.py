# -*- coding: utf-8 -*-
"""Hjelpeskript for å starte Tkinter-GUI uten å styre med PYTHONPATH.

Bruk:
  python run_admin_gui.py
  python run_admin_gui.py kildebibliotek.json
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.admin_gui import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
