from __future__ import annotations

"""rag_assistant.gui.relation_import_preview

D11: Modal forhåndsvisning/diff for relasjonsimport.

Mål:
- Brukeren skal trygt kunne importere relasjoner fra CSV/JSON
- Se *alle* endringer (ikke bare eksempler)
- Velge merge/replace
- Kun gjøre endringer når det faktisk er endringer (patch-semantikk)

Denne modulen er bevisst GUI-fokusert og testes primært via manuell bruk.
Den rene diff/apply-logikken testes i rag_assistant.relation_diff og
rag_assistant.relation_apply.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Optional

from ..kildebibliotek import Relation
from ..relation_diff import RelationDiff


def _fmt_note(note: Optional[str]) -> str:
    return (note or "").strip()


class RelationImportPreviewDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        file_name: str,
        scope_desc: str,
        diff: RelationDiff,
        warnings: List[str] | None = None,
        ignored_outside_scope: int = 0,
        default_mode: str = "merge",
        max_rows_per_tab: int = 5000,
    ) -> None:
        super().__init__(parent)

        self._parent = parent
        self._diff = diff
        self._warnings = list(warnings or [])
        self._ignored = int(ignored_outside_scope or 0)
        self._max_rows = int(max_rows_per_tab)

        self.result_mode: Optional[str] = None

        self.title("Importer relasjoner – forhåndsvisning")
        try:
            self.geometry("1050x650")
        except Exception:
            pass

        self.var_mode = tk.StringVar(value=(default_mode or "merge").strip().lower() or "merge")

        self._build_ui(file_name=file_name, scope_desc=scope_desc)
        self._populate()

        # modal
        try:
            self.transient(parent)
            self.grab_set()
        except Exception:
            pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def show(self) -> Optional[str]:
        self.wait_window(self)
        return self.result_mode

    # ---------------- UI ----------------

    def _build_ui(self, *, file_name: str, scope_desc: str) -> None:
        self.columnconfigure(0, weight=1)
        # Notebook ligger på rad 3 (header=0, summary=1, options=2)
        self.rowconfigure(3, weight=1)

        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Forhåndsvisning av relasjonsimport", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, text=f"Fil: {file_name}").grid(row=0, column=1, sticky="e")
        ttk.Label(header, text=f"Scope: {scope_desc}").grid(row=1, column=0, sticky="w", pady=(4, 0))

        # Summary + options
        summary = ttk.Labelframe(self, text="Oppsummering")
        summary.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        summary.columnconfigure(5, weight=1)

        d = self._diff
        items = [
            ("Eksisterende", str(d.existing_total)),
            ("I fil (rader)", str(d.incoming_total)),
            ("Unike", str(d.incoming_unique)),
            ("Nye", str(len(d.added))),
            ("Oppdateres", str(len(d.updated))),
            ("Uendret", str(len(d.unchanged))),
            ("Fjernes ved erstatt", str(len(d.removed))),
        ]

        for i, (k, v) in enumerate(items):
            ttk.Label(summary, text=f"{k}:").grid(row=0, column=i * 2, sticky="w", padx=(8, 2), pady=4)
            ttk.Label(summary, text=v, font=("Segoe UI", 9, "bold")).grid(
                row=0, column=i * 2 + 1, sticky="w", padx=(0, 10), pady=4
            )

        if self._ignored:
            ttk.Label(summary, text=f"Ignorert utenfor scope: {self._ignored}").grid(
                row=1, column=0, columnspan=6, sticky="w", padx=8, pady=(0, 6)
            )

        opt = ttk.Labelframe(self, text="Modus")
        opt.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))
        opt.columnconfigure(2, weight=1)

        ttk.Radiobutton(
            opt,
            text="Merge (patch) – legg til nye og oppdater note der det er endring",
            value="merge",
            variable=self.var_mode,
        ).grid(row=0, column=0, sticky="w", padx=8, pady=4)

        ttk.Radiobutton(
            opt,
            text="Erstatt – gjør scope identisk med fil (fjerner relasjoner som ikke er i fil)",
            value="replace",
            variable=self.var_mode,
        ).grid(row=1, column=0, sticky="w", padx=8, pady=4)

        # Notebook with lists
        self.nb = ttk.Notebook(self)
        self.nb.grid(row=3, column=0, sticky="nsew", padx=12, pady=(0, 8))

        self.tab_added = ttk.Frame(self.nb)
        self.tab_updated = ttk.Frame(self.nb)
        self.tab_removed = ttk.Frame(self.nb)
        self.tab_unchanged = ttk.Frame(self.nb)
        self.tab_warn = ttk.Frame(self.nb)

        self.nb.add(self.tab_added, text="Nye")
        self.nb.add(self.tab_updated, text="Oppdateres")
        self.nb.add(self.tab_removed, text="Fjernes ved erstatt")
        self.nb.add(self.tab_unchanged, text="Uendret")
        self.nb.add(self.tab_warn, text="Advarsler")

        self.tree_added, self.lbl_added = self._build_rel_tree(self.tab_added)
        self.tree_removed, self.lbl_removed = self._build_rel_tree(self.tab_removed)
        self.tree_unchanged, self.lbl_unchanged = self._build_rel_tree(self.tab_unchanged)

        self.tree_updated, self.lbl_updated = self._build_update_tree(self.tab_updated)

        self.txt_warn = tk.Text(self.tab_warn, height=10, wrap="word")
        self.txt_warn.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.txt_warn.configure(state="disabled")

        # Buttons
        btns = ttk.Frame(self)
        btns.grid(row=4, column=0, sticky="ew", padx=12, pady=(0, 12))
        btns.columnconfigure(0, weight=1)

        ttk.Button(btns, text="Kopier oppsummering", command=self._copy_summary).pack(side=tk.LEFT)
        ttk.Button(btns, text="Dry-run / Lukk", command=self._on_close).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Bruk", command=self._apply).pack(side=tk.RIGHT, padx=(0, 8))

    def _build_rel_tree(self, parent: ttk.Frame):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        lbl = ttk.Label(parent, text="")
        lbl.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))

        cols = ("from_id", "from_anchor", "type", "to_id", "to_anchor", "note")
        tree = ttk.Treeview(parent, columns=cols, show="headings")
        tree.heading("from_id", text="Fra")
        tree.heading("from_anchor", text="Anker fra")
        tree.heading("type", text="Type")
        tree.heading("to_id", text="Til")
        tree.heading("to_anchor", text="Anker til")
        tree.heading("note", text="Notat")

        tree.column("from_id", width=120)
        tree.column("from_anchor", width=120)
        tree.column("type", width=130)
        tree.column("to_id", width=120)
        tree.column("to_anchor", width=120)
        tree.column("note", width=350)

        vs = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vs.grid(row=1, column=1, sticky="ns", pady=8)

        return tree, lbl

    def _build_update_tree(self, parent: ttk.Frame):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        lbl = ttk.Label(parent, text="")
        lbl.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 0))

        cols = ("from_id", "from_anchor", "type", "to_id", "to_anchor", "old_note", "new_note")
        tree = ttk.Treeview(parent, columns=cols, show="headings")
        tree.heading("from_id", text="Fra")
        tree.heading("from_anchor", text="Anker fra")
        tree.heading("type", text="Type")
        tree.heading("to_id", text="Til")
        tree.heading("to_anchor", text="Anker til")
        tree.heading("old_note", text="Notat (før)")
        tree.heading("new_note", text="Notat (etter)")

        tree.column("from_id", width=120)
        tree.column("from_anchor", width=120)
        tree.column("type", width=130)
        tree.column("to_id", width=120)
        tree.column("to_anchor", width=120)
        tree.column("old_note", width=260)
        tree.column("new_note", width=260)

        vs = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vs.set)
        tree.grid(row=1, column=0, sticky="nsew", padx=(8, 0), pady=8)
        vs.grid(row=1, column=1, sticky="ns", pady=8)

        return tree, lbl

    # ---------------- Populate ----------------

    def _populate_rel_tree(self, tree: ttk.Treeview, rels: List[Relation]) -> int:
        tree.delete(*tree.get_children())
        n = 0
        for rel in rels:
            n += 1
            if n > self._max_rows:
                break
            tree.insert(
                "",
                tk.END,
                values=(
                    rel.from_id,
                    rel.from_anchor or "",
                    rel.relation_type,
                    rel.to_id,
                    rel.to_anchor or "",
                    _fmt_note(rel.note),
                ),
            )
        return n

    def _populate(self) -> None:
        d = self._diff

        shown_added = self._populate_rel_tree(self.tree_added, list(d.added))
        shown_removed = self._populate_rel_tree(self.tree_removed, list(d.removed))
        shown_unchanged = self._populate_rel_tree(self.tree_unchanged, list(d.unchanged))

        # Updated
        self.tree_updated.delete(*self.tree_updated.get_children())
        shown_updated = 0
        for u in d.updated:
            shown_updated += 1
            if shown_updated > self._max_rows:
                break
            self.tree_updated.insert(
                "",
                tk.END,
                values=(
                    u.new.from_id,
                    u.new.from_anchor or "",
                    u.new.relation_type,
                    u.new.to_id,
                    u.new.to_anchor or "",
                    _fmt_note(u.old.note),
                    _fmt_note(u.new.note),
                ),
            )

        self.lbl_added.configure(text=self._list_label("Nye", len(d.added), shown_added))
        self.lbl_updated.configure(text=self._list_label("Oppdateres", len(d.updated), shown_updated))
        self.lbl_removed.configure(text=self._list_label("Fjernes ved erstatt", len(d.removed), shown_removed))
        self.lbl_unchanged.configure(text=self._list_label("Uendret", len(d.unchanged), shown_unchanged))

        # warnings
        parts: List[str] = []
        if self._warnings:
            parts.append("Advarsler fra import:\n" + "\n".join(f"- {w}" for w in self._warnings))
        if self._ignored:
            parts.append(f"\nIgnorert utenfor scope: {self._ignored}")
        if not parts:
            parts.append("Ingen advarsler.")

        self.txt_warn.configure(state="normal")
        self.txt_warn.delete("1.0", tk.END)
        self.txt_warn.insert(tk.END, "\n\n".join(parts))
        self.txt_warn.configure(state="disabled")

        # Oppdater tab-titler med counts
        self.nb.tab(self.tab_added, text=f"Nye ({len(d.added)})")
        self.nb.tab(self.tab_updated, text=f"Oppdateres ({len(d.updated)})")
        self.nb.tab(self.tab_removed, text=f"Fjernes ved erstatt ({len(d.removed)})")
        self.nb.tab(self.tab_unchanged, text=f"Uendret ({len(d.unchanged)})")

    def _list_label(self, name: str, total: int, shown: int) -> str:
        if total <= self._max_rows:
            return f"{name}: {total}"
        return f"{name}: {total} (viser {shown} av {total})"

    # ---------------- Actions ----------------

    def _apply(self) -> None:
        m = (self.var_mode.get() or "").strip().lower()
        if m not in ("merge", "replace"):
            m = "merge"
        self.result_mode = m
        self.destroy()

    def _on_close(self) -> None:
        self.result_mode = None
        self.destroy()

    def _copy_summary(self) -> None:
        d = self._diff
        txt = (
            f"Eksisterende: {d.existing_total}\n"
            f"I fil (rader): {d.incoming_total}\n"
            f"Unike: {d.incoming_unique}\n"
            f"Nye: {len(d.added)}\n"
            f"Oppdateres: {len(d.updated)}\n"
            f"Uendret: {len(d.unchanged)}\n"
            f"Fjernes ved erstatt: {len(d.removed)}\n"
        )
        if self._ignored:
            txt += f"Ignorert utenfor scope: {self._ignored}\n"
        if self._warnings:
            txt += "\nAdvarsler:\n" + "\n".join(f"- {w}" for w in self._warnings)

        try:
            self.clipboard_clear()
            self.clipboard_append(txt)
        except Exception:
            pass
