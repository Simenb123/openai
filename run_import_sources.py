# -*- coding: utf-8 -*-
"""Hjelpeskript: importer kilder fra en mappe til kildebibliotek.json.

Bruk:
  python run_import_sources.py kilder
  python run_import_sources.py kilder --library kildebibliotek.json

Dette er nyttig hvis du ønsker å etablere et ryddig repo-format der hver kilde ligger i
egen mappe med valgfri `source.json`, og du vil generere/oppdatere biblioteket automatisk.

Merk:
- Importen indekserer IKKE. Etter import må du kjøre indeksering (GUI eller run_build_index.py).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.kildebibliotek import load_library, save_library  # noqa: E402
from rag_assistant.source_folder_import import import_sources_into_library  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Importer kilder fra mappe til kildebibliotek.json")
    parser.add_argument("source_folder", help="Mappe med kilder (standardformat)")
    parser.add_argument("--library", default="kildebibliotek.json", help="Path til kildebibliotek.json")
    args = parser.parse_args(argv)

    lib_path = Path(args.library)
    lib = load_library(lib_path)

    res = import_sources_into_library(lib, args.source_folder, base_dir=lib_path.parent)
    save_library(lib, lib_path)

    print(f"Importert/oppdatert {res.sources_added_or_updated} kilder -> {lib_path}")
    if res.warnings:
        print("\nAdvarsler:")
        for w in res.warnings[:50]:
            print(f"- {w}")
        if len(res.warnings) > 50:
            print(f"... ({len(res.warnings) - 50} flere)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
