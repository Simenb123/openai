# -*- coding: utf-8 -*-
"""Hjelpeskript for å kjøre qa_cli uten å styre med PYTHONPATH.

Bruk:
  python run_qa_cli.py "Spørsmål her"
  python run_qa_cli.py --show-context "Hva sier ISA 320 om vesentlighet?"
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.qa_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
