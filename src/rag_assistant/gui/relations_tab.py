from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..anchor_validation import AnchorCheck, check_anchor
from ..kildebibliotek import Library, Relation
from .anchor_tree_panel import AnchorTreePanel
from .filtering import filter_relations
from .relation_mapping_panel import RelationMappingPanel
from .relation_proposals_panel import RelationProposalsPanel
from .relation_type_guidance import RelationTypeGuidanceMixin
from .relations_anchor_helpers import RelationsAnchorHelpersMixin
from .relations_io_helpers import RelationsIOHelpersMixin


class RelationsTabMixin(RelationTypeGuidanceMixin, RelationsAnchorHelpersMixin, RelationsIOHelpersMixin):
    """Funksjonalitet for "Relasjoner"-fanen.

    Inkluderer:
    - Relasjonsliste (venstre) med filter
    - Skjema for ny relasjon / rediger relasjon (høyre)
    - Anker-autocomplete + "Vis"-dialog (søk/velg/kopier)
    - Anker-validering (advarsel ved ukjent anker)
    - Hierarkisk anker-navigasjon (tre)
    - Relasjonstype-forslag + maler
    - Forslagspanel (skann og foreslå)
    - Kartlegging (wizard for ankernivå)

    D7 (UX):
    - Filter for relasjonslisten
    - Dobbeltklikk for å laste relasjon inn i skjema for redigering
    - "dirty state" markeres når relasjoner endres
    """

    library_path: Path
    library: Library
    status: tk.StringVar
    anchor_inventory_path: Path
    anchor_inventory: dict

    # Widgets settes i _build_relations_tab
    rel_tree: ttk.Treeview
    cmb_from: ttk.Combobox
    cmb_to: ttk.Combobox
    cmb_from_anchor: ttk.Combobox
    cmb_to_anchor: ttk.Combobox
    txt_rel_note: tk.Text
    var_rel_from: tk.StringVar
    var_rel_to: tk.StringVar
    var_rel_type: tk.StringVar
    var_rel_from_anchor: tk.StringVar
    var_rel_to_anchor: tk.StringVar

    # D4/D5: types + templates
    var_rel_type_desc: tk.StringVar
    var_rel_direction_hint: tk.StringVar
    var_rel_template: tk.StringVar
    var_rel_template_desc: tk.StringVar
    cmb_rel_type: ttk.Combobox
    frm_rel_type_buttons: ttk.Frame
    cmb_rel_template: ttk.Combobox

    # D7
    var_rel_filter: tk.StringVar
    var_rel_list_info: tk.StringVar
    var_rel_form_title: tk.StringVar
    btn_rel_save: ttk.Button
    btn_rel_cancel: ttk.Button

    from_anchor_tree: AnchorTreePanel
    to_anchor_tree: AnchorTreePanel
    relation_proposals_panel: RelationProposalsPanel
    relation_mapping_panel: RelationMappingPanel

    def _build_relations_tab(self, parent: ttk.Frame) -> None:
        self._editing_relation_key: str | None = None
        self._rel_row_map: dict[str, str] = {}

        left = ttk.Frame(parent)
        right = ttk.Frame(parent)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8, pady=8)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Filter
        self.var_rel_filter = tk.StringVar(value="")
        self.var_rel_list_info = tk.StringVar(value="")
        frm_filter = ttk.Frame(left)
        frm_filter.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(frm_filter, text="Filter:").pack(side=tk.LEFT)
        ttk.Entry(frm_filter, textvariable=self.var_rel_filter).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        ttk.Label(frm_filter, textvariable=self.var_rel_list_info).pack(side=tk.RIGHT)
        self.var_rel_filter.trace_add("write", lambda *_: self._refresh_relations_list())

        cols = ("from_id", "from_anchor", "type", "to_id", "to_anchor")
        self.rel_tree = ttk.Treeview(left, columns=cols, show="headings", height=22)
        self.rel_tree.heading("from_id", text="Fra")
        self.rel_tree.heading("from_anchor", text="Anker fra")
        self.rel_tree.heading("type", text="Type")
        self.rel_tree.heading("to_id", text="Til")
        self.rel_tree.heading("to_anchor", text="Anker til")
        self.rel_tree.column("from_id", width=130)
        self.rel_tree.column("from_anchor", width=110)
        self.rel_tree.column("type", width=120)
        self.rel_tree.column("to_id", width=130)
        self.rel_tree.column("to_anchor", width=110)
        self.rel_tree.pack(fill=tk.BOTH, expand=True)
        self.rel_tree.bind("<Double-1>", lambda _e: self._load_selected_relation_to_form())

        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Slett relasjon", command=self._delete_relation).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Lagre bibliotek", command=self._save_library).pack(side=tk.LEFT, padx=6)

        io_row = ttk.Frame(left)
        io_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(io_row, text="Importer relasjoner…", command=self._import_relations).pack(side=tk.LEFT)
        ttk.Button(io_row, text="Eksporter relasjoner…", command=self._export_relations).pack(side=tk.LEFT, padx=6)

        io_row2 = ttk.Frame(left)
        io_row2.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(io_row2, text="Importer par (Fra→Til)…", command=self._import_relations_pair).pack(side=tk.LEFT)
        ttk.Button(io_row2, text="Eksporter par (Fra→Til)…", command=self._export_relations_pair).pack(
            side=tk.LEFT, padx=6
        )

        # Ny relasjon / rediger
        self.var_rel_form_title = tk.StringVar(value="Ny relasjon")
        ttk.Label(right, textvariable=self.var_rel_form_title, font=("Segoe UI", 11, "bold")).pack(anchor="w")

        info_row = ttk.Frame(right)
        info_row.pack(fill=tk.X, pady=(4, 8))
        self.var_anchor_info = tk.StringVar(value=f"Ankerliste: {self.anchor_inventory_path.name}")
        ttk.Label(info_row, textvariable=self.var_anchor_info).pack(side=tk.LEFT)
        ttk.Button(info_row, text="Oppdater ankere", command=self._reload_anchor_inventory).pack(side=tk.RIGHT)

        # Høyre side deles i (1) skjema og (2) anker-tre + forslag
        pw = ttk.PanedWindow(right, orient=tk.VERTICAL)
        pw.pack(fill=tk.BOTH, expand=True)

        frm_form = ttk.Frame(pw)
        frm_nav = ttk.Frame(pw)
        pw.add(frm_form, weight=3)
        pw.add(frm_nav, weight=2)

        # --- Skjema ---
        frm_form.columnconfigure(1, weight=1)

        self.var_rel_from = tk.StringVar()
        self.var_rel_to = tk.StringVar()
        self.var_rel_type = tk.StringVar(value="RELATES_TO")
        self.var_rel_from_anchor = tk.StringVar()
        self.var_rel_to_anchor = tk.StringVar()

        # D4: GUI-hjelp for relasjonstype
        self.var_rel_type_desc = tk.StringVar(value="")
        self.var_rel_direction_hint = tk.StringVar(value="")

        # D5: maler
        self.var_rel_template = tk.StringVar(value="")
        self.var_rel_template_desc = tk.StringVar(value="")

        ttk.Label(frm_form, text="Fra:").grid(row=0, column=0, sticky="w", pady=4)
        frm_from = ttk.Frame(frm_form)
        frm_from.grid(row=0, column=1, sticky="ew", pady=4)
        frm_from.columnconfigure(0, weight=1)
        self.cmb_from = ttk.Combobox(frm_from, textvariable=self.var_rel_from, state="readonly")
        self.cmb_from.grid(row=0, column=0, sticky="ew")
        ttk.Button(frm_from, text="Bytt Fra/Til", command=self._swap_from_to).grid(row=0, column=1, padx=(6, 0))
        self.cmb_from.bind("<<ComboboxSelected>>", lambda _e: self._refresh_anchor_dropdowns())

        ttk.Label(frm_form, text="Anker fra:").grid(row=1, column=0, sticky="w", pady=4)
        frm_from_anchor = ttk.Frame(frm_form)
        frm_from_anchor.grid(row=1, column=1, sticky="ew", pady=4)
        frm_from_anchor.columnconfigure(0, weight=1)
        self.cmb_from_anchor = ttk.Combobox(frm_from_anchor, textvariable=self.var_rel_from_anchor, state="normal")
        self.cmb_from_anchor.grid(row=0, column=0, sticky="ew")
        self.cmb_from_anchor.bind("<KeyRelease>", lambda _e: self._filter_anchor_values("from"))
        ttk.Button(
            frm_from_anchor,
            text="Vis",
            width=6,
            command=lambda: self._open_anchor_picker("from"),
        ).grid(row=0, column=1, padx=(6, 0))

        ttk.Label(frm_form, text="Type:").grid(row=2, column=0, sticky="w", pady=4)
        self.cmb_rel_type = ttk.Combobox(
            frm_form,
            values=[],
            textvariable=self.var_rel_type,
            state="readonly",
        )
        self.cmb_rel_type.grid(row=2, column=1, sticky="ew", pady=4)
        self.cmb_rel_type.bind("<<ComboboxSelected>>", lambda _e: self._refresh_relation_type_help())

        # D4/D5: forslag + forklaring (relasjonstype) + maler
        ttk.Label(frm_form, text="Forslag:").grid(row=3, column=0, sticky="nw", pady=4)
        frm_sugg = ttk.Frame(frm_form)
        frm_sugg.grid(row=3, column=1, sticky="ew", pady=4)
        frm_sugg.columnconfigure(0, weight=1)

        self.lbl_rel_type_desc = ttk.Label(frm_sugg, textvariable=self.var_rel_type_desc)
        self.lbl_rel_type_desc.grid(row=0, column=0, sticky="w")

        self.lbl_rel_dir_hint = ttk.Label(frm_sugg, textvariable=self.var_rel_direction_hint)
        self.lbl_rel_dir_hint.grid(row=1, column=0, sticky="w", pady=(2, 0))

        self.frm_rel_type_buttons = ttk.Frame(frm_sugg)
        self.frm_rel_type_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))

        # D5: templates
        frm_tmpl = ttk.Frame(frm_sugg)
        frm_tmpl.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        frm_tmpl.columnconfigure(0, weight=1)

        ttk.Label(frm_tmpl, text="Mal:").grid(row=0, column=0, sticky="w")
        self.cmb_rel_template = ttk.Combobox(frm_tmpl, textvariable=self.var_rel_template, state="readonly")
        self.cmb_rel_template.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        self.cmb_rel_template.bind("<<ComboboxSelected>>", lambda _e: self._refresh_relation_template_help())
        ttk.Button(frm_tmpl, text="Bruk mal", command=self._apply_selected_template).grid(row=0, column=2, padx=(6, 0))
        frm_tmpl.columnconfigure(1, weight=1)

        ttk.Label(frm_sugg, textvariable=self.var_rel_template_desc).grid(row=4, column=0, sticky="w", pady=(4, 0))

        ttk.Label(frm_form, text="Til:").grid(row=4, column=0, sticky="w", pady=4)
        self.cmb_to = ttk.Combobox(frm_form, textvariable=self.var_rel_to, state="readonly")
        self.cmb_to.grid(row=4, column=1, sticky="ew", pady=4)
        self.cmb_to.bind("<<ComboboxSelected>>", lambda _e: self._refresh_anchor_dropdowns())

        ttk.Label(frm_form, text="Anker til:").grid(row=5, column=0, sticky="w", pady=4)
        frm_to_anchor = ttk.Frame(frm_form)
        frm_to_anchor.grid(row=5, column=1, sticky="ew", pady=4)
        frm_to_anchor.columnconfigure(0, weight=1)
        self.cmb_to_anchor = ttk.Combobox(frm_to_anchor, textvariable=self.var_rel_to_anchor, state="normal")
        self.cmb_to_anchor.grid(row=0, column=0, sticky="ew")
        self.cmb_to_anchor.bind("<KeyRelease>", lambda _e: self._filter_anchor_values("to"))
        ttk.Button(
            frm_to_anchor,
            text="Vis",
            width=6,
            command=lambda: self._open_anchor_picker("to"),
        ).grid(row=0, column=1, padx=(6, 0))

        ttk.Label(frm_form, text="Notat:").grid(row=6, column=0, sticky="nw", pady=4)
        self.txt_rel_note = tk.Text(frm_form, height=6)
        self.txt_rel_note.grid(row=6, column=1, sticky="nsew", pady=4)
        frm_form.rowconfigure(6, weight=1)

        # --- Anker-navigasjon + forslag ---
        nb = ttk.Notebook(frm_nav)
        nb.pack(fill=tk.BOTH, expand=True)
        self.rel_sub_nb = nb  # D7: for navigasjon fra Oversikt

        tab_from = ttk.Frame(nb)
        tab_to = ttk.Frame(nb)
        tab_prop = ttk.Frame(nb)
        tab_map = ttk.Frame(nb)
        nb.add(tab_from, text="Fra-ankere (tre)")
        nb.add(tab_to, text="Til-ankere (tre)")
        nb.add(tab_prop, text="Forslag")
        nb.add(tab_map, text="Kartlegging")

        self.from_anchor_tree = AnchorTreePanel(
            tab_from,
            title="Fra: velg anker",
            get_source_id=lambda: self.var_rel_from.get().strip(),
            get_anchors_for_source=self._anchors_for_source,
            on_use_anchor=lambda a: self.var_rel_from_anchor.set(a),
        )
        self.from_anchor_tree.pack(fill=tk.BOTH, expand=True)

        self.to_anchor_tree = AnchorTreePanel(
            tab_to,
            title="Til: velg anker",
            get_source_id=lambda: self.var_rel_to.get().strip(),
            get_anchors_for_source=self._anchors_for_source,
            on_use_anchor=lambda a: self.var_rel_to_anchor.set(a),
        )
        self.to_anchor_tree.pack(fill=tk.BOTH, expand=True)

        # Forslagspanel
        self.relation_proposals_panel = RelationProposalsPanel(
            tab_prop,
            library=self.library,
            library_path=self.library_path,
            anchor_inventory=self.anchor_inventory,
            get_from_id=lambda: self.var_rel_from.get(),
            get_to_id=lambda: self.var_rel_to.get(),
            on_add_relations=self._add_relations_bulk,
            on_status=lambda msg: self.status.set(msg),
            run_task=getattr(self, "run_task", None),
        )
        self.relation_proposals_panel.pack(fill=tk.BOTH, expand=True)

        # Kartlegging
        self.relation_mapping_panel = RelationMappingPanel(
            tab_map,
            library=self.library,
            library_path=self.library_path,
            anchor_inventory=self.anchor_inventory,
            get_from_id=lambda: self.var_rel_from.get(),
            get_to_id=lambda: self.var_rel_to.get(),
            get_relation_type=lambda: self.var_rel_type.get(),
            get_note=lambda: (self.txt_rel_note.get("1.0", tk.END) or "").strip(),
            on_add_relations=self._add_relations_bulk,
            on_remove_relations=self._remove_relations_bulk,
            on_status=lambda msg: self.status.set(msg),
        )
        self.relation_mapping_panel.pack(fill=tk.BOTH, expand=True)

        # Actions
        action_row = ttk.Frame(right)
        action_row.pack(fill=tk.X, pady=(8, 0))

        self.btn_rel_cancel = ttk.Button(action_row, text="Avbryt redigering", command=self._cancel_edit_relation)
        self.btn_rel_cancel.pack(side=tk.LEFT)

        self.btn_rel_save = ttk.Button(action_row, text="Legg til relasjon", command=self._add_relation)
        self.btn_rel_save.pack(side=tk.RIGHT)

        # initial refresh
        self.from_anchor_tree.refresh_source()
        self.to_anchor_tree.refresh_source()
        self._refresh_relation_type_suggestions()
        self._refresh_relation_type_help()
        self._refresh_relation_template_help()
        self._update_edit_mode_ui()

    def _refresh_relations_list(self) -> None:
        self.rel_tree.delete(*self.rel_tree.get_children())
        self._rel_row_map = {}

        all_rels = sorted(
            list(self.library.relations),
            key=lambda r: (
                r.from_id,
                r.to_id,
                r.relation_type,
                r.from_anchor or "",
                r.to_anchor or "",
            ),
        )
        q = self.var_rel_filter.get() if hasattr(self, "var_rel_filter") else ""
        rels = filter_relations(all_rels, q)
        self._relations_view = rels

        for idx, rel in enumerate(rels):
            iid = f"rel_{idx}"
            self._rel_row_map[iid] = rel.key()
            self.rel_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(rel.from_id, rel.from_anchor or "", rel.relation_type, rel.to_id, rel.to_anchor or ""),
            )

        if hasattr(self, "var_rel_list_info"):
            self.var_rel_list_info.set(f"{len(rels)}/{len(all_rels)}")

        if hasattr(self, "_refresh_dashboard"):
            try:
                self._refresh_dashboard()
            except Exception:
                pass

        # D8: oppdater kartleggingspanelets fremdrift/status
        if hasattr(self, "relation_mapping_panel"):
            try:
                self.relation_mapping_panel.refresh_relation_state()
            except Exception:
                pass


# ---------------- Bulk add (D5) ----------------

    def _add_relations_bulk(self, relations: list[Relation]) -> None:
        for r in relations:
            self.library.upsert_relation(r)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)
        self._refresh_relations_list()

    def _remove_relations_bulk(self, relations: list[Relation]) -> None:
        for r in relations:
            self.library.remove_relation(r)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)
        self._refresh_relations_list()

    # ---------------- Editing helpers (D7) ----------------

    def _find_relation_by_key(self, key: str) -> Relation | None:
        for r in self.library.relations:
            if r.key() == key:
                return r
        return None

    def _load_selected_relation_to_form(self) -> None:
        sel = self.rel_tree.selection()
        if not sel:
            return
        iid = sel[0]
        key = self._rel_row_map.get(iid)
        if not key:
            return
        rel = self._find_relation_by_key(key)
        if not rel:
            return

        self._editing_relation_key = rel.key()

        self.var_rel_from.set(rel.from_id)
        self.var_rel_to.set(rel.to_id)
        self.var_rel_type.set(rel.relation_type)
        self.var_rel_from_anchor.set(rel.from_anchor or "")
        self.var_rel_to_anchor.set(rel.to_anchor or "")

        # Oppdater dropdowns (ankere avhenger av Fra/Til)
        self._refresh_anchor_dropdowns()

        self.txt_rel_note.delete("1.0", tk.END)
        if rel.note:
            self.txt_rel_note.insert(tk.END, rel.note)

        self._refresh_relation_type_help()
        self._refresh_relation_type_suggestions()
        self._update_edit_mode_ui()
        self.status.set("Redigerer valgt relasjon (dobbeltklikk igjen for å bytte)")

    def _cancel_edit_relation(self) -> None:
        self._editing_relation_key = None
        self.var_rel_from_anchor.set("")
        self.var_rel_to_anchor.set("")
        self.txt_rel_note.delete("1.0", tk.END)
        self._update_edit_mode_ui()
        self.status.set("Klar for ny relasjon")

    def _update_edit_mode_ui(self) -> None:
        is_edit = self._editing_relation_key is not None
        self.var_rel_form_title.set("Rediger relasjon" if is_edit else "Ny relasjon")
        try:
            self.btn_rel_save.configure(text="Lagre relasjon" if is_edit else "Legg til relasjon")
            self.btn_rel_cancel.configure(state=("normal" if is_edit else "disabled"))
        except Exception:
            pass

    # ---------------- Relations actions ----------------

    def _format_anchor_check(self, chk: AnchorCheck) -> str:
        if chk.status == "missing_inventory":
            return (
                f"- Kilde '{chk.source_id}': Ingen ankerliste funnet (ikke indeksert ennå?)\n"
                f"  Anker: {chk.normalized_anchor}"
            )
        if chk.status == "empty_inventory":
            return (
                f"- Kilde '{chk.source_id}': Ankerlisten er tom\n"
                f"  Anker: {chk.normalized_anchor}"
            )
        if chk.status == "unknown_anchor":
            sug = ", ".join(chk.suggestions) if chk.suggestions else "(ingen forslag)"
            return (
                f"- Kilde '{chk.source_id}': Anker finnes ikke i listen ({chk.anchors_count} ankere)\n"
                f"  Anker: {chk.normalized_anchor}\n"
                f"  Forslag: {sug}"
            )
        return ""

    def _add_relation(self) -> None:
        from_id = self.var_rel_from.get().strip()
        to_id = self.var_rel_to.get().strip()
        if not from_id or not to_id:
            messagebox.showerror("Feil", "Fra og Til må fylles ut")
            return

        rel = Relation(
            from_id=from_id,
            to_id=to_id,
            relation_type=self.var_rel_type.get().strip() or "RELATES_TO",
            from_anchor=self.var_rel_from_anchor.get().strip() or None,
            to_anchor=self.var_rel_to_anchor.get().strip() or None,
            note=(self.txt_rel_note.get("1.0", tk.END).strip() or None),
        )

        # Valider ankere (advarsel, ikke hard blokkering)
        checks: list[AnchorCheck] = []
        if rel.from_anchor:
            c = check_anchor(self.anchor_inventory, rel.from_id, rel.from_anchor)
            if not c.is_ok():
                checks.append(c)
        if rel.to_anchor:
            c = check_anchor(self.anchor_inventory, rel.to_id, rel.to_anchor)
            if not c.is_ok():
                checks.append(c)

        if checks:
            msg = "Anker-validering:\n\n" + "\n\n".join(self._format_anchor_check(c) for c in checks)
            msg += "\n\nVil du lagre relasjonen likevel?"
            if not messagebox.askyesno("Ukjent anker", msg):
                self.status.set("Relasjon ikke lagret (anker må korrigeres)")
                return

        # Hvis vi redigerer og nøkkel endres: fjern gammel relasjon
        if self._editing_relation_key is not None:
            old_key = self._editing_relation_key
            if old_key != rel.key():
                old = self._find_relation_by_key(old_key)
                if old:
                    self.library.remove_relation(old)

        self.library.upsert_relation(rel)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)

        self._refresh_relations_list()
        self.status.set("Relasjon lagret")

        # Avslutt redigering etter lagring
        self._editing_relation_key = None
        self._update_edit_mode_ui()

    def _delete_relation(self) -> None:
        sel = self.rel_tree.selection()
        if not sel:
            return
        iid = sel[0]
        key = self._rel_row_map.get(iid)
        if not key:
            return
        rel = self._find_relation_by_key(key)
        if not rel:
            return

        if messagebox.askyesno("Slett", "Slette valgt relasjon?"):
            self.library.remove_relation(rel)
            if hasattr(self, "_set_dirty"):
                self._set_dirty(True)
            # hvis vi redigerer samme relasjon -> reset
            if self._editing_relation_key == key:
                self._cancel_edit_relation()
            self._refresh_relations_list()
