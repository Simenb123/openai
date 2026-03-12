from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from ..kildebibliotek import Relation
from ..relation_proposals import ProposedRelation, propose_relations_for_pair


class RelationProposalsPanel(ttk.Frame):
    """GUI-panel for å generere og godkjenne relasjonsforslag (D5).

    D7: Kan kjøre skann i bakgrunnen via `run_task`.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        library: Any,
        library_path: Path,
        anchor_inventory: Dict[str, Any],
        get_from_id: Callable[[], str],
        get_to_id: Callable[[], str],
        on_add_relations: Callable[[List[Relation]], None],
        on_status: Callable[[str], None],
        run_task: Optional[Callable[..., bool]] = None,
    ) -> None:
        super().__init__(parent)
        self._library = library
        self._library_path = library_path
        self._anchor_inventory = anchor_inventory
        self._get_from_id = get_from_id
        self._get_to_id = get_to_id
        self._on_add_relations = on_add_relations
        self._on_status = on_status
        self._run_task = run_task

        self._var_only_known = tk.BooleanVar(value=True)
        self._var_info = tk.StringVar(value="")

        self._proposals: List[ProposedRelation] = []
        self._selected: Dict[str, bool] = {}  # iid -> bool

        self._build_ui()

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=(8, 6))

        ttk.Button(top, text="Skann og foreslå", command=self._scan).pack(side=tk.LEFT)
        ttk.Checkbutton(top, text="Kun kjente ankere", variable=self._var_only_known).pack(side=tk.LEFT, padx=(10, 0))
        ttk.Label(top, textvariable=self._var_info).pack(side=tk.RIGHT)

        cols = ("sel", "from_anchor", "to_anchor", "type", "occ", "known")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        self._tree.heading("sel", text="✔")
        self._tree.heading("from_anchor", text="Fra-anker")
        self._tree.heading("to_anchor", text="Til-anker")
        self._tree.heading("type", text="Type")
        self._tree.heading("occ", text="#")
        self._tree.heading("known", text="Kjent")
        self._tree.column("sel", width=40, anchor=tk.CENTER)
        self._tree.column("from_anchor", width=120)
        self._tree.column("to_anchor", width=140)
        self._tree.column("type", width=120)
        self._tree.column("occ", width=40, anchor=tk.E)
        self._tree.column("known", width=60, anchor=tk.CENTER)
        self._tree.pack(fill=tk.BOTH, expand=True, padx=8)

        self._tree.bind("<Button-1>", self._on_tree_click)

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=8, pady=8)

        ttk.Button(btns, text="Velg alle", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(btns, text="Fjern valg", command=self._clear_selection).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btns, text="Legg til valgte", command=self._add_selected).pack(side=tk.RIGHT)

    def set_anchor_inventory(self, inv: Dict[str, Any]) -> None:
        self._anchor_inventory = inv

    def _set_info(self, msg: str) -> None:
        self._var_info.set(msg or "")

    def _render_result(self, res) -> None:
        self._proposals = res.proposals
        self._selected = {}

        self._tree.delete(*self._tree.get_children())

        for idx, p in enumerate(self._proposals):
            iid = f"p{idx}"
            self._selected[iid] = True if p.known_target_anchor else False  # auto-velg kjente
            sel_txt = "☑" if self._selected[iid] else "☐"
            self._tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    sel_txt,
                    p.relation.from_anchor or "",
                    p.relation.to_anchor or "",
                    p.relation.relation_type,
                    p.occurrences,
                    "Ja" if p.known_target_anchor else "Nei",
                ),
            )

        info = f"{len(self._proposals)} forslag"
        if res.warnings:
            info += f" • {len(res.warnings)} advarsler"
            self._on_status("; ".join(res.warnings[:2]))
        self._set_info(info)

    def _scan(self) -> None:
        from_id = self._get_from_id().strip()
        to_id = self._get_to_id().strip()
        if not from_id or not to_id:
            messagebox.showinfo("Info", "Velg både Fra og Til først")
            return

        def _work():
            return propose_relations_for_pair(
                self._library,
                from_source_id=from_id,
                to_source_id=to_id,
                anchor_inventory=self._anchor_inventory,
                base_dir=self._library_path.parent,
                include_unknown_anchors=not self._var_only_known.get(),
            )

        def _ok(res) -> None:
            self._render_result(res)

        def _err(e: Exception) -> None:
            self._set_info("")
            messagebox.showerror("Feil", f"Skann feilet: {e}")

        # Bakgrunn hvis mulig
        if callable(self._run_task):
            self._set_info("Skanner…")
            self._run_task(
                f"scan_{from_id}_{to_id}",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message=f"Skanner {from_id} → {to_id}…",
                done_message="Skann ferdig",
            )
        else:
            self._set_info("Skanner…")
            self.update_idletasks()
            try:
                res = _work()
                _ok(res)
            except Exception as e:
                _err(e)

    def _on_tree_click(self, event: tk.Event) -> None:
        iid = self._tree.identify_row(event.y)
        col = self._tree.identify_column(event.x)
        if not iid:
            return
        # toggle i første kolonne
        if col == "#1":
            self._selected[iid] = not self._selected.get(iid, False)
            sel_txt = "☑" if self._selected[iid] else "☐"
            vals = list(self._tree.item(iid, "values"))
            if vals:
                vals[0] = sel_txt
                self._tree.item(iid, values=tuple(vals))

    def _select_all(self) -> None:
        for iid in self._tree.get_children(""):
            self._selected[iid] = True
            vals = list(self._tree.item(iid, "values"))
            if vals:
                vals[0] = "☑"
                self._tree.item(iid, values=tuple(vals))

    def _clear_selection(self) -> None:
        for iid in self._tree.get_children(""):
            self._selected[iid] = False
            vals = list(self._tree.item(iid, "values"))
            if vals:
                vals[0] = "☐"
                self._tree.item(iid, values=tuple(vals))

    def _add_selected(self) -> None:
        rels: List[Relation] = []
        for iid in self._tree.get_children(""):
            if not self._selected.get(iid, False):
                continue
            idx = int(iid[1:])  # p{idx}
            if idx < 0 or idx >= len(self._proposals):
                continue
            rels.append(self._proposals[idx].relation)

        if not rels:
            messagebox.showinfo("Info", "Ingen valgte forslag")
            return

        self._on_add_relations(rels)
        self._on_status(f"La til {len(rels)} relasjoner fra forslag")
        messagebox.showinfo("OK", f"La til {len(rels)} relasjoner")
