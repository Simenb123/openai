# -*- coding: utf-8 -*-
"""Kjør golden questions / retrieval-evaluering.

Bruk:
  python run_eval_golden.py golden/golden_isa230.json --show

Tips:
  - Krever at du har bygget indeks (Chroma) på forhånd.
  - Krever embeddings for query (OpenAI), så .env må være satt opp.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.env_loader import load_env  # noqa: E402
from rag_assistant.golden_eval import load_golden_cases, run_golden_eval, save_report  # noqa: E402
from rag_assistant.rag_index import get_or_create_collection  # noqa: E402
from rag_assistant.settings_profiles import load_settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Golden questions – retrieval-evaluering")
    parser.add_argument("golden_path", nargs="?", default="golden/golden_isa230.json")
    parser.add_argument("--db", default=None, help="Chroma db-path (default fra settings/env)")
    parser.add_argument("--collection", default=None, help="Collection-navn (default fra settings/env)")
    parser.add_argument("--library", default=None, help="Path til kildebibliotek.json (valgfri)")
    parser.add_argument("--k", type=int, default=5, help="Antall treff i retrieval per case")
    parser.add_argument("--no-relations", action="store_true", help="Ikke ekspander relasjoner")
    parser.add_argument("--out", default=None, help="Output path for rapport (json)")
    parser.add_argument("--show", action="store_true", help="Skriv kort oppsummering til stdout")

    args = parser.parse_args(argv)

    load_env()
    cfg = load_settings()
    db_path = args.db or cfg.db_path
    collection_name = args.collection or cfg.collection

    try:
        col = get_or_create_collection(
            db_path=db_path,
            collection_name=collection_name,
            embedding_model=cfg.embedding_model,
        )
    except Exception as e:
        print(f"Kunne ikke åpne collection: {e}")
        return 1

    golden_path = Path(args.golden_path)
    if not golden_path.exists():
        print(f"Finner ikke golden-fil: {golden_path}")
        return 2

    cases = load_golden_cases(golden_path)
    if not cases:
        print("Ingen cases i golden-fil")
        return 2

    report = run_golden_eval(
        cases,
        collection=col,
        library_path=args.library,
        n_results=max(1, int(args.k)),
        expand_relations=not args.no_relations,
    )

    out = Path(args.out) if args.out else Path("eval_reports") / "golden_report.json"
    save_report(report, out)

    if args.show:
        print(f"Golden eval: {report['passed']}/{report['cases']} bestått")
        if report.get("failed"):
            print("Feil-cases:")
            for r in report.get("results") or []:
                if not r.get("pass_all"):
                    print(f"- {r.get('case_id')}: {r.get('question')}")
        print(f"Rapport lagret: {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
