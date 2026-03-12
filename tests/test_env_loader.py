# -*- coding: utf-8 -*-
import os
from pathlib import Path

from rag_assistant.env_loader import load_env


def test_load_env_custom_path(tmp_path: Path, monkeypatch) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("OPENAI_API_KEY=TESTKEY\nX_FOO=bar\n", encoding="utf-8")

    # sørg for at variabelen ikke er satt fra før
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    load_env(dotenv_path=str(env_file))

    assert os.environ["OPENAI_API_KEY"] == "TESTKEY"
    # andre nøkler skal også lastes
    assert os.environ["X_FOO"] == "bar"
