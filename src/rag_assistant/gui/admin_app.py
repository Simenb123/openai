from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..anchor_inventory import inventory_path_for_library, load_anchor_inventory
from ..kildebibliotek import Library, load_library
from .dashboard_tab import DashboardTabMixin
from .qa_tab import QATabMixin
from .relations_tab import RelationsTabMixin
from .sources_tab import SourcesTabMixin
from .task_runner import TkTaskRunner


class AdminApp(tk.Tk, DashboardTabMixin, SourcesTabMixin, RelationsTabMixin, QATabMixin):
    """Tkinter admin-app for kildebibliotek + relasjoner.

    Deles opp i mixins for å holde filstørrelser nede.

    D7 (UX):
    - Hurtigstart-tab (Oversikt)
    - "dirty state" (viser * i tittel og spør ved avslutning)
    - Bakgrunnsoppgaver for tunge operasjoner (indeksering/skann)
    """

    library_path: Path
    library: Library
    anchor_inventory_path: Path
    anchor_inventory: dict

    def __init__(self, library_path: Path) -> None:
        super().__init__()
        self._dirty = False

        self.title("RAG Admin – Kildebibliotek")
        self.geometry("1120x700")

        self.library_path = library_path
        self.library = load_library(library_path)

        # Anker-inventory (autocomplete for relasjoner)
        self.anchor_inventory_path = inventory_path_for_library(library_path)
        self.anchor_inventory = load_anchor_inventory(self.anchor_inventory_path)

        self.status = tk.StringVar(value=f"Bibliotek: {self.library_path}")

        self._build_ui()
        self._refresh_sources_list()
        self._refresh_relations_list()
        self._refresh_anchor_dropdowns()

        # Confirm on close if unsaved
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- UX helpers ----------------

    def _set_dirty(self, dirty: bool = True) -> None:
        self._dirty = bool(dirty)
        title = "RAG Admin – Kildebibliotek"
        if self._dirty:
            title += " *"
        self.title(title)

    def _on_close(self) -> None:
        if self._dirty:
            if messagebox.askyesno("Lagre?", "Du har endringer som ikke er lagret. Vil du lagre før du avslutter?"):
                try:
                    self._save_library()
                except Exception:
                    pass
        self.destroy()

    # ---------------- Task runner ----------------

    def run_task(
        self,
        name: str,
        func,
        *,
        on_success=None,
        on_error=None,
        start_message: str | None = None,
        done_message: str | None = None,
    ) -> bool:
        """Kjør en oppgave i bakgrunnen.

        Returnerer False hvis en oppgave allerede kjører.
        """
        ok = self._task_runner.run(
            name,
            func,
            on_success=on_success,
            on_error=on_error,
            start_message=start_message,
            done_message=done_message,
        )
        if not ok:
            messagebox.showinfo("Info", "Det kjører allerede en oppgave. Vent til den er ferdig.")
        return ok

    # ---------------- Navigation ----------------

    def _select_tab(self, name: str) -> None:
        idx = self._tab_index.get(name)
        if idx is None:
            return
        try:
            self.nb.select(idx)
        except Exception:
            pass

    def _open_relations_subtab(self, name: str) -> None:
        # rel_sub_nb settes i RelationsTabMixin
        if not hasattr(self, "rel_sub_nb"):
            return
        try:
            nb = getattr(self, "rel_sub_nb")
            # finn tab index ved å sammenligne label
            for i in range(nb.index("end")):
                if str(nb.tab(i, "text")) == name:
                    nb.select(i)
                    break
        except Exception:
            pass

    # ---------------- UI build ----------------

    def _build_ui(self) -> None:
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill=tk.BOTH, expand=True)

        self._tab_index: dict[str, int] = {}

        tab_dash = ttk.Frame(self.nb)
        self.nb.add(tab_dash, text="Oversikt")
        self._tab_index["Oversikt"] = 0
        self._build_dashboard_tab(tab_dash)

        tab_sources = ttk.Frame(self.nb)
        self.nb.add(tab_sources, text="Kilder")
        self._tab_index["Kilder"] = 1
        self._build_sources_tab(tab_sources)

        tab_rel = ttk.Frame(self.nb)
        self.nb.add(tab_rel, text="Relasjoner")
        self._tab_index["Relasjoner"] = 2
        self._build_relations_tab(tab_rel)

        tab_qa = ttk.Frame(self.nb)
        self.nb.add(tab_qa, text="QA / Test")
        self._tab_index["QA / Test"] = 3
        self._build_qa_tab(tab_qa)

        # Status bar with progress
        status_frame = ttk.Frame(self)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.columnconfigure(0, weight=1)

        ttk.Label(status_frame, textvariable=self.status).grid(row=0, column=0, sticky="ew", padx=8, pady=4)
        self._progress = ttk.Progressbar(status_frame, mode="indeterminate", length=180)
        self._progress.grid(row=0, column=1, sticky="e", padx=8)

        self._task_runner = TkTaskRunner(self, progressbar=self._progress, status_var=self.status)
