from __future__ import annotations

"""rag_assistant.gui.relations_io_helpers

D9: Import/eksport av relasjoner (CSV/JSON) i GUI.

Denne logikken er flyttet ut av relations_tab.py for å holde filstørrelsen nede.

Host forventes å tilby:
- self.library (kildebibliotek.Library)
- self.status (tk.StringVar)
- self.var_rel_filter (tk.StringVar) [valgfritt]
- self._relations_view (list[Relation]) [valgfritt, settes i _refresh_relations_list]
- self._refresh_relations_list()
- self._set_dirty(True/False) [valgfritt, finnes i AdminApp]
"""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple

from ..kildebibliotek import Relation
from ..relation_apply import apply_relation_import
from ..relation_diff import compute_relation_diff
from ..relation_io import (
    export_relations_to_csv,
    export_relations_to_json,
    import_relations_from_csv,
    import_relations_from_json,
)

from .relation_import_preview import RelationImportPreviewDialog


class RelationsIOHelpersMixin:
    status: tk.StringVar
    library: object

    def _current_pair(self) -> Optional[Tuple[str, str]]:
        """Returnerer (from_id, to_id) fra skjemaet, hvis tilgjengelig."""
        if not hasattr(self, "var_rel_from") or not hasattr(self, "var_rel_to"):
            return None
        fid = getattr(self, "var_rel_from").get().strip()  # type: ignore[attr-defined]
        tid = getattr(self, "var_rel_to").get().strip()  # type: ignore[attr-defined]
        if not fid or not tid:
            return None
        return fid, tid

    def _load_relations_file(self, path: Path):
        if path.suffix.lower() == ".json":
            return import_relations_from_json(path)
        return import_relations_from_csv(path)

    def _save_relations_file(self, relations: List[Relation], path: Path) -> int:
        if path.suffix.lower() == ".json":
            return export_relations_to_json(relations, path)
        if path.suffix.lower() != ".csv":
            path = path.with_suffix(".csv")
        return export_relations_to_csv(relations, path, delimiter=";")

    def _relations_for_pair(self, from_id: str, to_id: str) -> List[Relation]:
        fid = (from_id or "").strip()
        tid = (to_id or "").strip()
        all_rels = list(getattr(self.library, "relations", []) or [])
        return [r for r in all_rels if r.from_id == fid and r.to_id == tid]

    def _export_relations(self) -> None:
        """Eksporter relasjoner til CSV/JSON.

        - Hvis filter er aktivt, spør vi om eksport skal ta med kun filtrerte eller alle.
        - CSV eksporteres med semikolon (;) som standard, som ofte fungerer bedre i norsk Excel.
        """
        q = self.var_rel_filter.get().strip() if hasattr(self, "var_rel_filter") else ""
        filtered = getattr(self, "_relations_view", None)
        if filtered is None:
            filtered = list(getattr(self.library, "relations", []) or [])
        all_rels = list(getattr(self.library, "relations", []) or [])

        if q:
            choice = messagebox.askyesnocancel(
                "Eksporter",
                f"Filter er aktivt: '{q}'.\n\n"
                f"Eksportere kun filtrerte relasjoner ({len(filtered)})?\n\n"
                "Ja = kun filtrerte\nNei = alle\nAvbryt = avbryt",
            )
            if choice is None:
                return
            rels_to_export = filtered if choice else all_rels
        else:
            rels_to_export = all_rels

        if not rels_to_export:
            messagebox.showinfo("Info", "Ingen relasjoner å eksportere.")
            return

        fp = filedialog.asksaveasfilename(
            title="Eksporter relasjoner",
            defaultextension=".csv",
            filetypes=[
                ("CSV (Excel-vennlig)", "*.csv"),
                ("JSON", "*.json"),
                ("Alle filer", "*.*"),
            ],
        )
        if not fp:
            return

        p = Path(fp)

        try:
            n = self._save_relations_file(rels_to_export, p)

            self.status.set(f"Eksporterte {n} relasjoner til {p.name}")
            messagebox.showinfo("OK", f"Eksporterte {n} relasjoner til:\n{p}")
        except Exception as e:
            messagebox.showerror("Feil", f"Kunne ikke eksportere relasjoner:\n{e}")

    def _export_relations_pair(self) -> None:
        """Eksporter relasjoner for valgt Fra→Til (paret i skjemaet)."""
        pair = self._current_pair()
        if not pair:
            messagebox.showinfo("Info", "Velg både Fra og Til i skjemaet først.")
            return
        from_id, to_id = pair

        all_pair = self._relations_for_pair(from_id, to_id)
        if not all_pair:
            messagebox.showinfo("Info", f"Ingen relasjoner funnet for paret {from_id} → {to_id}.")
            return

        # Hvis filter er aktivt: spør om vi skal eksportere kun filtrerte innenfor paret
        q = self.var_rel_filter.get().strip() if hasattr(self, "var_rel_filter") else ""
        view = getattr(self, "_relations_view", None)
        if view is None:
            view = list(getattr(self.library, "relations", []) or [])
        filtered_pair = [r for r in view if r.from_id == from_id and r.to_id == to_id]

        rels_to_export = all_pair
        if q:
            choice = messagebox.askyesnocancel(
                "Eksporter par",
                f"Filter er aktivt: '{q}'.\n\n"
                f"Eksportere kun filtrerte relasjoner innenfor paret ({len(filtered_pair)})?\n\n"
                "Ja = kun filtrerte i paret\nNei = alle i paret\nAvbryt = avbryt",
            )
            if choice is None:
                return
            rels_to_export = filtered_pair if choice else all_pair

        default_name = f"relations_{from_id}__{to_id}.csv"
        fp = filedialog.asksaveasfilename(
            title=f"Eksporter relasjoner for {from_id} → {to_id}",
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[
                ("CSV (Excel-vennlig)", "*.csv"),
                ("JSON", "*.json"),
                ("Alle filer", "*.*"),
            ],
        )
        if not fp:
            return
        p = Path(fp)

        try:
            n = self._save_relations_file(rels_to_export, p)
            self.status.set(f"Eksporterte {n} relasjoner ({from_id}→{to_id})")
            messagebox.showinfo("OK", f"Eksporterte {n} relasjoner for {from_id} → {to_id} til:\n{p}")
        except Exception as e:
            messagebox.showerror("Feil", f"Kunne ikke eksportere relasjoner:\n{e}")

    def _import_relations(self) -> None:
        """Importer relasjoner fra CSV/JSON.

        Brukeren kan velge:
        - Erstatte alle eksisterende relasjoner, eller
        - Slå sammen (upsert) inn i eksisterende relasjonskart.
        """
        fp = filedialog.askopenfilename(
            title="Importer relasjoner",
            filetypes=[
                ("Relasjoner (CSV/JSON)", "*.csv *.json"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
                ("Alle filer", "*.*"),
            ],
        )
        if not fp:
            return

        p = Path(fp)
        self._import_relations_from_path(p, scope_pair=None)

    def _import_relations_pair(self) -> None:
        """Importer relasjoner fra fil, men kun for valgt Fra→Til."""
        pair = self._current_pair()
        if not pair:
            messagebox.showinfo("Info", "Velg både Fra og Til i skjemaet først.")
            return

        fp = filedialog.askopenfilename(
            title="Importer relasjoner for valgt par (CSV/JSON)",
            filetypes=[
                ("Relasjoner (CSV/JSON)", "*.csv *.json"),
                ("CSV", "*.csv"),
                ("JSON", "*.json"),
                ("Alle filer", "*.*"),
            ],
        )
        if not fp:
            return

        p = Path(fp)
        self._import_relations_from_path(p, scope_pair=pair)

    # ---------------- Internal import implementation (D10) ----------------

    def _import_relations_from_path(self, path: Path, *, scope_pair: Optional[Tuple[str, str]]) -> None:
        """Importer relasjoner med forhåndsvisning/diff.

        - scope_pair=None -> global import
        - scope_pair=(from_id, to_id) -> importer kun relasjoner for paret
        """
        try:
            res = self._load_relations_file(path)
        except Exception as e:
            messagebox.showerror("Feil", f"Kunne ikke importere relasjoner:\n{e}")
            return

        incoming_raw = list(res.relations)
        incoming_scoped = list(incoming_raw)
        ignored_outside = 0
        scope_desc = "Alle relasjoner"

        if scope_pair is not None:
            from_id, to_id = scope_pair
            scope_desc = f"Kun paret {from_id} → {to_id}"
            filtered = [r for r in incoming_scoped if r.from_id == from_id and r.to_id == to_id]
            ignored_outside = len(incoming_scoped) - len(filtered)
            incoming_scoped = filtered

        if not incoming_scoped:
            msg = f"Ingen relasjoner ble importert ({scope_desc})."
            if ignored_outside:
                msg += f"\n\nIgnorerte {ignored_outside} relasjoner utenfor scope."
            if res.warnings:
                w = res.warnings[:20]
                msg += "\n\nAdvarsler (utdrag):\n- " + "\n- ".join(w)
                if len(res.warnings) > len(w):
                    msg += f"\n... ({len(res.warnings) - len(w)} flere)"
            messagebox.showinfo("Import", msg)
            return

        # Existing scope
        if scope_pair is None:
            existing_scope = list(getattr(self.library, "relations", []) or [])
        else:
            existing_scope = self._relations_for_pair(scope_pair[0], scope_pair[1])

        # D11: Full forhåndsvisning i eget vindu
        diff = compute_relation_diff(existing_scope, incoming_scoped)
        dlg = RelationImportPreviewDialog(
            self,
            file_name=path.name,
            scope_desc=scope_desc,
            diff=diff,
            warnings=res.warnings,
            ignored_outside_scope=ignored_outside,
            default_mode="merge",
        )
        mode = dlg.show()
        if mode is None:
            return

        # Ikke gjør endringer hvis det ikke er noe å gjøre
        if mode == "merge" and (len(diff.added) == 0 and len(diff.updated) == 0):
            self.status.set("Import: Ingen endringer (merge)")
            messagebox.showinfo("Import", "Ingen endringer å bruke (merge/patch).")
            return
        if mode == "replace" and (len(diff.added) == 0 and len(diff.updated) == 0 and len(diff.removed) == 0):
            self.status.set("Import: Ingen endringer (erstatt)")
            messagebox.showinfo("Import", "Ingen endringer å bruke (erstatt).")
            return

        # Apply via testbar funksjon
        apply_res = apply_relation_import(
            list(getattr(self.library, "relations", []) or []),
            incoming_raw,
            mode=mode,
            scope_pair=scope_pair,
        )

        self.library.relations = apply_res.new_relations  # type: ignore[attr-defined]

        if hasattr(self, "_set_dirty"):
            self._set_dirty(True)  # type: ignore[attr-defined]

        if hasattr(self, "_refresh_relations_list"):
            self._refresh_relations_list()  # type: ignore[attr-defined]

        # Status + info
        d = apply_res.diff
        self.status.set(
            f"Import ({mode}) – nye: {len(d.added)}, oppdaterte: {len(d.updated)}"
            + (f", fjernet: {len(d.removed)}" if mode == "replace" else "")
        )

        done = f"Import fullført ({scope_desc})\n\n"
        done += f"Nye: {len(d.added)}\nOppdaterte: {len(d.updated)}\nUendret: {len(d.unchanged)}"
        if mode == "replace":
            done += f"\nFjernet: {len(d.removed)}"
        if ignored_outside:
            done += f"\nIgnorert utenfor scope: {ignored_outside}"
        messagebox.showinfo("Import fullført", done)
