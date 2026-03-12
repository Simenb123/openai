from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..anchor_inventory import load_anchor_inventory
from ..env_loader import load_env
from ..settings_profiles import load_settings


class DashboardTabMixin:
    """Hurtigstart/oversikt-tab.

    Fokus: brukervennlighet + effektivitet.

    Denne fanen skal gjøre det tydelig:
    1) hvor man starter
    2) hva som må gjøres i hvilken rekkefølge
    3) hva som er "status" for bibliotek/ankere/relasjoner

    Host (AdminApp) forventes å tilby:
      - self.library, self.library_path, self.anchor_inventory_path
      - self.status (tk.StringVar)
      - handlinger fra SourcesTabMixin / RelationsTabMixin
      - self._select_tab('Kilder'/'Relasjoner'/'QA / Test')
      - self._open_relations_subtab('Kartlegging'/'Forslag') (valgfri)
    """

    library_path: Path
    anchor_inventory_path: Path

    def _build_dashboard_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        header = ttk.Frame(parent)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Hurtigstart", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, sticky="w")
        self._var_dash_info = tk.StringVar(value="")
        ttk.Label(header, textvariable=self._var_dash_info).grid(row=0, column=1, sticky="e")

        # Statusbokser
        grid = ttk.Frame(parent)
        grid.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)
        grid.columnconfigure(2, weight=1)

        # --- Kilder ---
        box_sources = ttk.Labelframe(grid, text="1) Kilder")
        box_sources.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
        box_sources.columnconfigure(0, weight=1)

        self._var_sources_status = tk.StringVar(value="")
        ttk.Label(
            box_sources,
            text="Legg inn kilder (standardformat mappe), og lagre biblioteket.",
            wraplength=280,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))
        ttk.Label(box_sources, textvariable=self._var_sources_status).grid(row=1, column=0, sticky="w", padx=10)

        btns = ttk.Frame(box_sources)
        btns.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))
        ttk.Button(btns, text="Importer kildemap…", command=self._import_source_folder).pack(side=tk.LEFT)
        ttk.Button(btns, text="Gå til Kilder", command=lambda: self._select_tab("Kilder")).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns, text="Lagre bibliotek", command=self._save_library).pack(side=tk.RIGHT)

        # --- Indeks ---
        box_index = ttk.Labelframe(grid, text="2) Indeks / Ankere")
        box_index.grid(row=0, column=1, sticky="nsew", padx=(0, 10), pady=(0, 10))
        box_index.columnconfigure(0, weight=1)

        ttk.Label(
            box_index,
            text="Bygg indeks for å få chunking + ankerliste (kildebibliotek.anchors.json).",
            wraplength=280,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        self._var_index_status = tk.StringVar(value="")
        ttk.Label(box_index, textvariable=self._var_index_status).grid(row=1, column=0, sticky="w", padx=10)

        btns2 = ttk.Frame(box_index)
        btns2.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))
        ttk.Button(btns2, text="Indekser alle", command=self._index_all).pack(side=tk.LEFT)
        ttk.Button(btns2, text="Oppdater ankere", command=self._reload_anchor_inventory).pack(side=tk.LEFT, padx=6)
        ttk.Button(btns2, text="Sjekk konfig", command=self._show_config_health).pack(side=tk.RIGHT)

        # --- Relasjoner ---
        box_rel = ttk.Labelframe(grid, text="3) Relasjoner")
        box_rel.grid(row=0, column=2, sticky="nsew", pady=(0, 10))
        box_rel.columnconfigure(0, weight=1)

        ttk.Label(
            box_rel,
            text="Relasjoner er valgfritt, men gir bedre presisjon (kontekstekspansjon).",
            wraplength=280,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 4))

        self._var_rel_status = tk.StringVar(value="")
        ttk.Label(box_rel, textvariable=self._var_rel_status).grid(row=1, column=0, sticky="w", padx=10)

        btns3 = ttk.Frame(box_rel)
        btns3.grid(row=2, column=0, sticky="ew", padx=10, pady=(8, 10))
        ttk.Button(btns3, text="Gå til Relasjoner", command=lambda: self._select_tab("Relasjoner")).pack(
            side=tk.LEFT
        )
        ttk.Button(btns3, text="Åpne Kartlegging", command=lambda: self._open_relations_subtab_safe("Kartlegging")).pack(
            side=tk.LEFT, padx=6
        )
        ttk.Button(btns3, text="Åpne Forslag", command=lambda: self._open_relations_subtab_safe("Forslag")).pack(
            side=tk.LEFT
        )

        # --- QA / Test ---
        box_qa = ttk.Labelframe(grid, text="4) Pilot / QA")
        box_qa.grid(row=1, column=0, columnspan=3, sticky="nsew")
        box_qa.columnconfigure(0, weight=1)

        ttk.Label(
            box_qa,
            text=(
                "Når du har indeksert, kan du teste med CLI:\n"
                "  python run_qa_cli.py --show-context \"Hva sier ISA 230 punkt 8?\"\n\n"
                "Tips: for en rask ende-til-ende pilot (indeks + golden-eval) kan du kjøre:\n"
                "  python run_pilot_isa230.py --library kildebibliotek.json --show\n\n"
                "Eller eval direkte:\n"
                "  python run_eval_golden.py golden/golden_isa230_pilot.json --show"
            ),
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(8, 6))

        frm_copy = ttk.Frame(box_qa)
        frm_copy.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))

        ttk.Button(frm_copy, text="Gå til QA / Test", command=lambda: self._select_tab("QA / Test")).pack(side=tk.LEFT)
        ttk.Button(frm_copy, text="Kopier QA-kommando", command=self._copy_qa_command).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_copy, text="Kopier eval-kommando", command=self._copy_eval_command).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_copy, text="Kopier pilot-kommando", command=self._copy_pilot_command).pack(side=tk.LEFT)
        ttk.Button(frm_copy, text="Kjør pilot (ISA 230)", command=self._run_pilot_isa230).pack(side=tk.LEFT, padx=6)
        ttk.Button(frm_copy, text="Oppdater oversikt", command=self._refresh_dashboard).pack(side=tk.RIGHT)

        self._refresh_dashboard()

    def _open_relations_subtab_safe(self, subtab_name: str) -> None:
        try:
            self._select_tab("Relasjoner")
            if hasattr(self, "_open_relations_subtab"):
                self._open_relations_subtab(subtab_name)
        except Exception:
            self._select_tab("Relasjoner")

    def _refresh_dashboard(self) -> None:
        # Oppdater toppinfo
        lib = getattr(self, "library", None)
        n_sources = len(getattr(lib, "sources", []) or []) if lib else 0
        n_rel = len(getattr(lib, "relations", []) or []) if lib else 0
        self._var_dash_info.set(f"Kilder: {n_sources} • Relasjoner: {n_rel}")

        self._var_sources_status.set(f"Bibliotek: {Path(self.library_path).name} • {n_sources} kilder")

        # Anker-status
        inv = load_anchor_inventory(self.anchor_inventory_path)
        gen = (inv or {}).get("generated_at")
        srcs = (inv or {}).get("sources") or {}
        n_with_anchors = 0
        n_anchors_total = 0
        for _sid, meta in srcs.items():
            c = int((meta or {}).get("anchor_count") or 0)
            if c > 0:
                n_with_anchors += 1
                n_anchors_total += c

        if gen:
            self._var_index_status.set(f"Ankerliste: {n_with_anchors} kilder • {n_anchors_total} ankere • sist: {gen}")
        else:
            self._var_index_status.set("Ankerliste: ikke generert ennå (trykk 'Indekser alle')")

        self._var_rel_status.set(f"{n_rel} relasjoner i biblioteket")

    def _copy_qa_command(self) -> None:
        cmd = 'python run_qa_cli.py --show-context "Hva sier ISA 230 punkt 8?"'
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.status.set("Kopierte QA-kommando til utklippstavlen")
        except Exception:
            pass

    def _copy_eval_command(self) -> None:
        cmd = "python run_eval_golden.py golden/golden_isa230_pilot.json --show"
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.status.set("Kopierte eval-kommando til utklippstavlen")
        except Exception:
            pass

    def _copy_pilot_command(self) -> None:
        cmd = "python run_pilot_isa230.py --library kildebibliotek.json --show"
        try:
            self.clipboard_clear()
            self.clipboard_append(cmd)
            self.status.set("Kopierte pilot-kommando til utklippstavlen")
        except Exception:
            pass

    def _run_pilot_isa230(self) -> None:
        """Kjører en enkel pilot i GUI (bakgrunnsoppgave).

        Dette gjør det enklere å teste uten å hoppe til terminalen.
        Krever at OPENAI_API_KEY er satt.
        """

        # Sjekk nøkkel først
        try:
            load_env()
        except Exception:
            pass

        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showinfo(
                "Mangler OPENAI_API_KEY",
                "OPENAI_API_KEY mangler. Legg den i .env i rot og prøv igjen.",
            )
            return

        wipe = messagebox.askyesno(
            "Pilot: wipe?",
            "Vil du wipe hele vektordatabasen (collection) før piloten?\n\n"
            "Ja = ren pilot (anbefalt hvis du vil være sikker)\n"
            "Nei = kun reindekser pilot-kilder (beholder øvrige kilder)",
        )

        def _work() -> dict:
            from ..anchor_inventory import inventory_path_for_library
            from ..build_index import build_index_from_library
            from ..golden_eval import load_golden_cases, run_golden_eval, save_report
            from ..pilot_isa230 import build_default_scope, subset_library_to_sources
            from ..rag_index import get_or_create_collection
            from ..settings_profiles import load_settings

            cfg = load_settings()
            lib_path = self.library_path
            scope = build_default_scope(self.library, include_optional=True)
            if scope.missing_required:
                raise RuntimeError(
                    "Mangler required kilder i biblioteket: " + ", ".join(scope.missing_required)
                )

            pilot_lib = subset_library_to_sources(self.library, scope.source_ids)
            inv_path = inventory_path_for_library(lib_path)

            # Indekser pilot-kilder
            build_index_from_library(
                pilot_lib,
                settings=cfg,
                wipe_collection=bool(wipe),
                purge_existing=True,
                anchor_inventory_path=inv_path,
                prune_anchor_inventory=False,
            )

            # Eval
            golden_path = Path("golden/golden_isa230_pilot.json")
            cases = load_golden_cases(golden_path)
            col = get_or_create_collection(
                db_path=cfg.db_path,
                collection_name=cfg.collection,
                embedding_model=cfg.embedding_model,
            )
            report = run_golden_eval(cases, collection=col, library_path=str(lib_path), n_results=5)
            Path("reports").mkdir(parents=True, exist_ok=True)
            report_path = Path("reports/golden_isa230_pilot_report.json")
            save_report(report, report_path)
            report["report_path"] = str(report_path)
            report["pilot_sources"] = scope.source_ids
            return report

        def _ok(report: dict) -> None:
            try:
                self._refresh_dashboard()
            except Exception:
                pass

            msg = (
                f"Pilot-kilder: {', '.join(report.get('pilot_sources', []))}\n"
                f"Golden eval: passed={report.get('passed')} failed={report.get('failed')} cases={report.get('cases')}\n\n"
                f"Rapport: {report.get('report_path')}"
            )
            messagebox.showinfo("Pilot ferdig", msg)

        def _err(e: Exception) -> None:
            messagebox.showerror("Pilot feilet", str(e))

        if hasattr(self, "run_task"):
            self.run_task(
                "pilot_isa230",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message="Kjører pilot (ISA 230)…",
                done_message="Pilot ferdig",
            )
        else:
            # fallback (kan fryse UI)
            try:
                report = _work()
                _ok(report)
            except Exception as e:
                _err(e)

    def _show_config_health(self) -> None:
        # Best-effort: last env og sjekk om OPENAI_API_KEY finnes.
        try:
            load_env()
        except Exception:
            pass

        api_ok = bool(os.environ.get("OPENAI_API_KEY"))
        env_path = Path.cwd() / ".env"
        env_ok = env_path.exists()

        cfg = None
        cfg_err = None
        try:
            cfg = load_settings()
        except Exception as e:
            cfg_err = str(e)

        lines = []
        lines.append(f".env: {'OK' if env_ok else 'Mangler'} ({env_path})")
        lines.append(f"OPENAI_API_KEY: {'OK' if api_ok else 'Mangler'}")

        if cfg_err:
            lines.append(f"Settings: Feil: {cfg_err}")
        elif cfg:
            lines.append(f"DB path: {cfg.db_path}")
            lines.append(f"Collection: {cfg.collection}")
            lines.append(f"Embedding-model: {cfg.embedding_model}")

        messagebox.showinfo("Konfig-sjekk", "\n".join(lines))
