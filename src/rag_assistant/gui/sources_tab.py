from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from ..anchor_inventory import load_anchor_inventory
from ..build_index import build_index_from_library
from ..env_loader import load_env
from ..kildebibliotek import Library, Source, save_library
from ..settings_profiles import load_settings
from ..source_folder_import import import_sources_into_library
from .anchor_picker import AnchorPickerDialog
from .constants import DOC_TYPES
from .filtering import filter_sources
from .util import safe_json_loads, try_make_relative_path


class SourcesTabMixin:
    """Funksjonalitet for "Kilder"-fanen."""

    # Disse attributtene settes av AdminApp
    library_path: Path
    library: Library
    status: tk.StringVar
    anchor_inventory_path: Path

    # Widgets settes i _build_sources_tab
    sources_tree: ttk.Treeview
    files_list: tk.Listbox
    txt_meta: tk.Text
    var_id: tk.StringVar
    var_type: tk.StringVar
    var_title: tk.StringVar
    var_tags: tk.StringVar

    # D7 filter
    var_source_filter: tk.StringVar

    def _build_sources_tab(self, parent: ttk.Frame) -> None:
        left = ttk.Frame(parent)
        right = ttk.Frame(parent)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=8, pady=8)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=8, pady=8)

        # Filter
        self.var_source_filter = tk.StringVar(value="")
        frm_filter = ttk.Frame(left)
        frm_filter.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(frm_filter, text="Filter:").pack(side=tk.LEFT)
        ent = ttk.Entry(frm_filter, textvariable=self.var_source_filter)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self.var_source_filter.trace_add("write", lambda *_: self._refresh_sources_list())

        # Liste over kilder
        cols = ("type", "title", "nfiles")
        self.sources_tree = ttk.Treeview(left, columns=cols, show="headings", height=22)
        self.sources_tree.heading("type", text="Type")
        self.sources_tree.heading("title", text="Tittel")
        self.sources_tree.heading("nfiles", text="#Filer")
        self.sources_tree.column("type", width=70)
        self.sources_tree.column("title", width=260)
        self.sources_tree.column("nfiles", width=60, anchor=tk.E)
        self.sources_tree.pack(fill=tk.BOTH, expand=True)
        self.sources_tree.bind("<<TreeviewSelect>>", lambda _e: self._on_select_source())

        # Buttons under list
        btn_row = ttk.Frame(left)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(btn_row, text="Ny", command=self._new_source).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Slett", command=self._delete_source).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Lagre bibliotek", command=self._save_library).pack(side=tk.LEFT, padx=6)

        ttk.Separator(left).pack(fill=tk.X, pady=10)

        ttk.Button(left, text="Importer kildemap…", command=self._import_source_folder).pack(fill=tk.X)
        ttk.Button(left, text="Indekser valgt", command=self._index_selected).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(left, text="Indekser alle", command=self._index_all).pack(fill=tk.X, pady=(6, 0))
        ttk.Button(left, text="Vis ankere for valgt", command=self._show_anchors_for_selected).pack(
            fill=tk.X, pady=(6, 0)
        )

        # Editor for selected source
        form = ttk.Frame(right)
        form.pack(fill=tk.BOTH, expand=True)

        def row(label: str, widget: tk.Widget, r: int) -> None:
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", padx=(0, 8), pady=4)
            widget.grid(row=r, column=1, sticky="ew", pady=4)

        form.columnconfigure(1, weight=1)

        self.var_id = tk.StringVar()
        self.var_type = tk.StringVar(value="OTHER")
        self.var_title = tk.StringVar()
        self.var_tags = tk.StringVar()

        row("ID (unik):", ttk.Entry(form, textvariable=self.var_id), 0)
        row("Type:", ttk.Combobox(form, values=DOC_TYPES, textvariable=self.var_type, state="readonly"), 1)
        row("Tittel:", ttk.Entry(form, textvariable=self.var_title), 2)
        row("Tags (kommasep):", ttk.Entry(form, textvariable=self.var_tags), 3)

        ttk.Label(form, text="Filer:").grid(row=4, column=0, sticky="nw", padx=(0, 8), pady=4)
        files_frame = ttk.Frame(form)
        files_frame.grid(row=4, column=1, sticky="nsew", pady=4)
        files_frame.columnconfigure(0, weight=1)

        self.files_list = tk.Listbox(files_frame, height=5)
        self.files_list.grid(row=0, column=0, sticky="nsew")

        btns = ttk.Frame(files_frame)
        btns.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        ttk.Button(btns, text="+", width=3, command=self._add_file).pack(pady=(0, 6))
        ttk.Button(btns, text="-", width=3, command=self._remove_file).pack()

        ttk.Label(form, text="Metadata (JSON):").grid(row=5, column=0, sticky="nw", padx=(0, 8), pady=4)
        self.txt_meta = tk.Text(form, height=12)
        self.txt_meta.grid(row=5, column=1, sticky="nsew", pady=4)
        form.rowconfigure(5, weight=1)

        ttk.Button(form, text="Lagre kilde", command=self._save_source).grid(row=6, column=1, sticky="e", pady=(8, 0))

    def _refresh_sources_list(self) -> None:
        self.sources_tree.delete(*self.sources_tree.get_children())

        sources = list(self.library.sources)
        # sort (stabil og lesbar)
        sources = sorted(sources, key=lambda s: (s.doc_type, s.title.lower(), s.id))

        q = self.var_source_filter.get() if hasattr(self, "var_source_filter") else ""
        sources = filter_sources(sources, q)

        for src in sources:
            self.sources_tree.insert("", tk.END, iid=src.id, values=(src.doc_type, src.title, len(src.files)))

        # Oppdater dropdowns i rel-tab hvis de finnes
        ids = [s.id for s in sorted(self.library.sources, key=lambda s: s.id)]
        if hasattr(self, "cmb_from"):
            self.cmb_from["values"] = ids
        if hasattr(self, "cmb_to"):
            self.cmb_to["values"] = ids

        # Oppdater anker-dropdowns hvis rel-tab er bygget
        if hasattr(self, "_refresh_anchor_dropdowns"):
            self._refresh_anchor_dropdowns()

        if hasattr(self, "_refresh_dashboard"):
            try:
                self._refresh_dashboard()
            except Exception:
                pass

    def _on_select_source(self) -> None:
        sel = self.sources_tree.selection()
        if not sel:
            return
        sid = sel[0]
        src = self.library.get_source(sid)
        if not src:
            return

        self.var_id.set(src.id)
        self.var_type.set(src.doc_type)
        self.var_title.set(src.title)
        self.var_tags.set(", ".join(src.tags))
        self.files_list.delete(0, tk.END)
        for f in src.files:
            self.files_list.insert(tk.END, f)

        self.txt_meta.delete("1.0", tk.END)
        self.txt_meta.insert(tk.END, json.dumps(src.metadata, ensure_ascii=False, indent=2))

    def _new_source(self) -> None:
        self.var_id.set("")
        self.var_type.set("OTHER")
        self.var_title.set("")
        self.var_tags.set("")
        self.files_list.delete(0, tk.END)
        self.txt_meta.delete("1.0", tk.END)

    def _save_source(self) -> None:
        sid = self.var_id.get().strip()
        if not sid:
            messagebox.showerror("Feil", "ID kan ikke være tom")
            return
        src = Source(
            id=sid,
            doc_type=self.var_type.get().strip() or "OTHER",
            title=self.var_title.get().strip() or sid,
            tags=[t.strip() for t in self.var_tags.get().split(",") if t.strip()],
            files=[self.files_list.get(i) for i in range(self.files_list.size())],
            metadata=safe_json_loads(self.txt_meta.get("1.0", tk.END)),
        )
        self.library.upsert_source(src)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)
        self._refresh_sources_list()
        self.status.set(f"Lagret kilde: {sid}")

    def _delete_source(self) -> None:
        sel = self.sources_tree.selection()
        if not sel:
            return
        sid = sel[0]
        if messagebox.askyesno("Slett", f"Slette {sid} og relasjoner?"):
            self.library.remove_source(sid, remove_relations=True)
            if hasattr(self, "_set_dirty"):
                self._set_dirty(True)
            self._refresh_sources_list()
            if hasattr(self, "_refresh_relations_list"):
                self._refresh_relations_list()
            self._new_source()

    def _add_file(self) -> None:
        fp = filedialog.askopenfilename(title="Velg fil", filetypes=[("Alle filer", "*.*")])
        if not fp:
            return
        self.files_list.insert(tk.END, try_make_relative_path(fp))

    def _remove_file(self) -> None:
        sel = self.files_list.curselection()
        if not sel:
            return
        self.files_list.delete(sel[0])

    def _save_library(self) -> None:
        save_library(self.library, self.library_path)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(False)
        self.status.set(f"Bibliotek lagret: {self.library_path}")
        if hasattr(self, "_refresh_dashboard"):
            try:
                self._refresh_dashboard()
            except Exception:
                pass

    # ---------------- Anchor browsing ----------------

    def _show_anchors_for_selected(self) -> None:
        sel = self.sources_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Velg en kilde først")
            return
        sid = sel[0]

        inv = load_anchor_inventory(self.anchor_inventory_path)
        sources = (inv or {}).get("sources") or {}
        entry = sources.get(sid)
        if not entry:
            messagebox.showinfo(
                "Info",
                f"Fant ingen ankerliste for '{sid}'.\n\n"
                "Tips: Indekser kilden (eller Indekser alle) for å generere ankerliste.",
            )
            return

        anchors = entry.get("anchors") or []
        if not anchors:
            messagebox.showinfo("Info", f"Ankerlisten for '{sid}' er tom.")
            return

        AnchorPickerDialog(self, source_id=sid, source_title=entry.get("title"), anchors=list(anchors), on_use=None)

    # ---------------- Indexing actions ----------------

    def _import_source_folder(self) -> None:
        folder = filedialog.askdirectory(title="Velg kildemap (standardformat)")
        if not folder:
            return
        res = import_sources_into_library(self.library, folder, base_dir=self.library_path.parent)
        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)
        self._refresh_sources_list()

        msg = f"Importert/oppdatert {res.sources_added_or_updated} kilder.\n\nHusk å lagre bibliotek."
        if res.warnings:
            w = res.warnings[:25]
            msg += "\n\nAdvarsler (utdrag):\n- " + "\n- ".join(w)
            if len(res.warnings) > len(w):
                msg += f"\n... ({len(res.warnings) - len(w)} flere)"

        messagebox.showinfo("Import", msg)
        self.status.set(f"Importerte {res.sources_added_or_updated} kilder fra {folder}")

    def _index_selected(self) -> None:
        sel = self.sources_tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Velg en kilde først")
            return
        sid = sel[0]
        src = self.library.get_source(sid)
        if not src:
            return

        partial = Library(version=self.library.version, sources=[src], relations=self.library.relations)

        def _work() -> int:
            load_env()
            cfg = load_settings()
            return int(
                build_index_from_library(
                    partial,
                    settings=cfg,
                    purge_existing=True,
                    wipe_collection=False,
                    anchor_inventory_path=self.anchor_inventory_path,
                    prune_anchor_inventory=False,
                )
            )

        def _ok(n: int) -> None:
            if hasattr(self, "_reload_anchor_inventory"):
                self._reload_anchor_inventory()
            messagebox.showinfo("OK", f"Indeksert {n} chunks for {sid}")
            self.status.set(f"Indeksert {sid}: {n} chunks")

        def _err(e: Exception) -> None:
            messagebox.showerror("Feil", f"Indeksering feilet: {e}")

        if hasattr(self, "run_task"):
            self.run_task(
                f"index_{sid}",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message=f"Indekserer {sid}…",
                done_message="Indeksering ferdig",
            )
        else:
            try:
                n = _work()
                _ok(n)
            except Exception as e:
                _err(e)

    def _index_all(self) -> None:
        def _work() -> int:
            load_env()
            cfg = load_settings()
            return int(
                build_index_from_library(
                    self.library,
                    settings=cfg,
                    wipe_collection=True,
                    anchor_inventory_path=self.anchor_inventory_path,
                    prune_anchor_inventory=True,
                )
            )

        def _ok(n: int) -> None:
            if hasattr(self, "_reload_anchor_inventory"):
                self._reload_anchor_inventory()
            messagebox.showinfo("OK", f"Indeksert {n} chunks totalt")
            self.status.set(f"Indeksert alle: {n} chunks")

        def _err(e: Exception) -> None:
            messagebox.showerror("Feil", f"Indeksering feilet: {e}")

        if hasattr(self, "run_task"):
            self.run_task(
                "index_all",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message="Indekserer alle kilder…",
                done_message="Indeksering ferdig",
            )
        else:
            try:
                n = _work()
                _ok(n)
            except Exception as e:
                _err(e)
