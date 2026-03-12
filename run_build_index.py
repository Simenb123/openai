# -*- coding: utf-8 -*-
"""Hjelpeskript for å bygge indeks uten å installere pakken.

Eksempler:
  python run_build_index.py --library kildebibliotek.json
  python run_build_index.py kilder
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.build_index import build_index_from_library_file, build_index_from_path  # noqa: E402
from rag_assistant.anchor_inventory import inventory_path_for_library  # noqa: E402
from rag_assistant.env_loader import load_env  # noqa: E402
from rag_assistant.settings_profiles import load_settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bygg / oppdater Chroma-indeks")
    parser.add_argument("path", nargs="?", default=None, help="Mappe/fil med kilder (valgfri)")
    parser.add_argument("--library", default=None, help="kildebibliotek.json (anbefalt)")
    parser.add_argument("--chunk-size", type=int, default=1200)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument(
        "--wipe",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Slett hele collection før indeksering (anbefalt ved --library for konsistens)",
    )
    args = parser.parse_args(argv)

    load_env()
    cfg = load_settings()

    try:
        if args.library:
            n = build_index_from_library_file(
                args.library,
                settings=cfg,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                wipe_collection=bool(args.wipe),
            )
            inv = inventory_path_for_library(args.library)
            print(f"Indeksert {n} chunks fra library: {args.library}")
            print(f"Oppdatert ankerliste: {inv}")
            return 0

        if args.path:
            n = build_index_from_path(
                args.path,
                settings=cfg,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                wipe_collection=bool(args.wipe),
            )
            print(f"Indeksert {n} chunks fra path: {args.path}")
            return 0

        print("Du må oppgi enten --library eller en path.")
        return 2
    except Exception as e:
        print(f"FEIL ved bygging av indeks: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
