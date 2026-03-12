"""Kjør en liten pilot med ISA 230.

Dette scriptet er ment som en *praktisk snarvei* for å komme i gang:

1) Laster .env + settings
2) Leser kildebibliotek.json
3) Indekserer pilot-kilder (default: ISA-230 + evt RL/RF hvis de finnes)
4) Kjører golden-eval og lagrer rapport i reports/

Bruk:
  python run_pilot_isa230.py --library kildebibliotek.json

Tips:
  - Legg OPENAI_API_KEY i .env først
  - Bruk --wipe hvis du vil starte helt rent (sletter hele collection)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.is_dir():
    sys.path.insert(0, str(SRC))

from rag_assistant.anchor_inventory import inventory_path_for_library  # noqa: E402
from rag_assistant.build_index import build_index_from_library  # noqa: E402
from rag_assistant.env_loader import load_env  # noqa: E402
from rag_assistant.golden_eval import load_golden_cases, run_golden_eval, save_report  # noqa: E402
from rag_assistant.kildebibliotek import load_library  # noqa: E402
from rag_assistant.pilot_isa230 import build_default_scope, subset_library_to_sources  # noqa: E402
from rag_assistant.rag_index import get_or_create_collection  # noqa: E402
from rag_assistant.settings_profiles import load_settings  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--library", default="kildebibliotek.json", help="Path til kildebibliotek.json")
    ap.add_argument(
        "--golden",
        default="golden/golden_isa230_pilot.json",
        help="Golden-fil (json) for piloten",
    )
    ap.add_argument("--wipe", action="store_true", help="Slett hele collection før indeksering")
    ap.add_argument("--no-index", action="store_true", help="Ikke bygg indeks (forutsetter at indeks finnes)")
    ap.add_argument("--no-eval", action="store_true", help="Ikke kjør eval")
    ap.add_argument("--n-results", type=int, default=5, help="Antall retrieval-resultater per spørsmål")
    ap.add_argument("--no-relations", action="store_true", help="Ikke bruk relasjonsbasert ekspansjon")
    ap.add_argument("--show", action="store_true", help="Skriv kort rapport til stdout")
    args = ap.parse_args()

    load_env()
    cfg = load_settings()

    lib_path = Path(args.library)
    if not lib_path.exists():
        print(f"Fant ikke bibliotekfil: {lib_path}", file=sys.stderr)
        return 2

    library = load_library(lib_path)
    scope = build_default_scope(library, include_optional=True)

    if scope.missing_required:
        print(
            "Piloten kan ikke kjøres fordi følgende kilder mangler i biblioteket: "
            + ", ".join(scope.missing_required),
            file=sys.stderr,
        )
        print("Tips: legg inn ISA-230 som Source i kildebibliotek.json (eller importer via GUI).", file=sys.stderr)
        return 2

    pilot_lib = subset_library_to_sources(library, scope.source_ids)

    inv_path = inventory_path_for_library(lib_path)

    if not args.no_index:
        n = build_index_from_library(
            pilot_lib,
            settings=cfg,
            wipe_collection=bool(args.wipe),
            purge_existing=True,
            anchor_inventory_path=inv_path,
            prune_anchor_inventory=False,  # ikke fjern andre kilder fra inventory ved pilot
        )
        if args.show:
            print(f"Indeksert {n} chunks for pilot-kilder: {', '.join(scope.source_ids)}")

    if args.no_eval:
        return 0

    golden_path = Path(args.golden)
    if not golden_path.exists():
        print(f"Fant ikke golden-fil: {golden_path}", file=sys.stderr)
        return 2

    cases = load_golden_cases(golden_path)

    col = get_or_create_collection(db_path=cfg.db_path, collection_name=cfg.collection, embedding_model=cfg.embedding_model)
    report = run_golden_eval(
        cases,
        collection=col,
        library_path=str(lib_path),
        n_results=max(1, int(args.n_results)),
        expand_relations=not bool(args.no_relations),
    )

    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "golden_isa230_pilot_report.json"
    save_report(report, report_path)

    if args.show:
        print(f"Golden eval: passed={report['passed']} failed={report['failed']} cases={report['cases']}")
        print(f"Rapport: {report_path}")

    return 0 if int(report.get("failed") or 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
