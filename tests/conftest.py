import os
import sys
from pathlib import Path

import pytest

# Sørg for at src/ er på sys.path i tester
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.is_dir() and str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch):
    # Dummy key slik at moduler som forventer key ikke feiler bare ved import/instansiering.
    monkeypatch.setenv("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "test-key"))
    monkeypatch.setenv("OPENAI_CHAT_MODEL", os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"))
    monkeypatch.setenv("OPENAI_EMBED_MODEL", os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small"))
