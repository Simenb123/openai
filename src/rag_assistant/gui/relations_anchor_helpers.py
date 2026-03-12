from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Dict, List

from ..anchor_inventory import load_anchor_inventory
from ..anchor_validation import anchors_for_source
from .anchor_picker import AnchorPickerDialog


class RelationsAnchorHelpersMixin:
    """Mixin for anker-relatert GUI-logikk i Relasjoner-fanen.

    Flyttet ut fra relations_tab.py i D5 for å holde filstørrelse nede og gjøre
    videre utvikling enklere.
    """

    anchor_inventory_path: Any
    anchor_inventory: Dict[str, Any]
    status: tk.StringVar

    var_rel_from: tk.StringVar
    var_rel_to: tk.StringVar
    var_rel_from_anchor: tk.StringVar
    var_rel_to_anchor: tk.StringVar

    cmb_from_anchor: ttk.Combobox
    cmb_to_anchor: ttk.Combobox

    def _anchors_for_source(self, source_id: str) -> list[str]:
        return anchors_for_source(self.anchor_inventory, source_id)

    def _refresh_anchor_dropdowns(self) -> None:
        # GUI bygges før comboboxene finnes
        if not hasattr(self, "cmb_from_anchor") or not hasattr(self, "cmb_to_anchor"):
            return
        from_id = self.var_rel_from.get().strip()
        to_id = self.var_rel_to.get().strip()
        self.cmb_from_anchor["values"] = self._anchors_for_source(from_id)
        self.cmb_to_anchor["values"] = self._anchors_for_source(to_id)

        # D3: oppdater også tre-panelene hvis de finnes
        if hasattr(self, "from_anchor_tree"):
            self.from_anchor_tree.refresh_source()  # type: ignore[attr-defined]
        if hasattr(self, "to_anchor_tree"):
            self.to_anchor_tree.refresh_source()  # type: ignore[attr-defined]

        # D4: oppdater relasjonstypeforslag basert på valgt Fra/Til
        if hasattr(self, "cmb_rel_type"):
            try:
                self._refresh_relation_type_suggestions()  # type: ignore[attr-defined]
            except Exception:
                pass

        # D6: oppdater kartleggingspanel ved endring av Fra/Til
        if hasattr(self, "relation_mapping_panel"):
            try:
                self.relation_mapping_panel.refresh_lists()  # type: ignore[attr-defined]
            except Exception:
                pass

    def _filter_anchor_values(self, which: str) -> None:
        """Typeahead filtering for combobox values.

        Vi bruker prefix-match for å holde det raskt.
        """
        if which == "from":
            sid = self.var_rel_from.get().strip()
            typed = self.var_rel_from_anchor.get().strip()
            cmb = getattr(self, "cmb_from_anchor", None)
        else:
            sid = self.var_rel_to.get().strip()
            typed = self.var_rel_to_anchor.get().strip()
            cmb = getattr(self, "cmb_to_anchor", None)

        if cmb is None:
            return

        anchors = self._anchors_for_source(sid)
        if typed:
            t = "".join(typed.split()).upper()
            anchors = [a for a in anchors if "".join(a.split()).upper().startswith(t)]
        cmb["values"] = anchors[:1500]

    def _reload_anchor_inventory(self) -> None:
        self.anchor_inventory = load_anchor_inventory(self.anchor_inventory_path)
        self._refresh_anchor_dropdowns()
        # D5: oppdater forslagspanel hvis det finnes
        if hasattr(self, "relation_proposals_panel"):
            try:
                self.relation_proposals_panel.set_anchor_inventory(self.anchor_inventory)  # type: ignore[attr-defined]
            except Exception:
                pass
        # D6: oppdater kartleggingspanel hvis det finnes
        if hasattr(self, "relation_mapping_panel"):
            try:
                self.relation_mapping_panel.set_anchor_inventory(self.anchor_inventory)  # type: ignore[attr-defined]
            except Exception:
                pass
        gen = (self.anchor_inventory or {}).get("generated_at")
        if gen:
            self.status.set(f"Ankerliste oppdatert ({gen})")
        else:
            self.status.set("Ankerliste lastet")

        # D7: oppdater Oversikt hvis den finnes
        if hasattr(self, "_refresh_dashboard"):
            try:
                self._refresh_dashboard()  # type: ignore[attr-defined]
            except Exception:
                pass

    def _open_anchor_picker(self, which: str) -> None:
        """Åpner dialog for å søke/velge ankere for valgt kilde."""
        which = (which or "").strip().lower()
        if which not in ("from", "to"):
            return

        source_id = self.var_rel_from.get().strip() if which == "from" else self.var_rel_to.get().strip()
        if not source_id:
            messagebox.showinfo("Info", "Velg en kilde først")
            return

        anchors = self._anchors_for_source(source_id)
        sources = (self.anchor_inventory or {}).get("sources") or {}
        entry = sources.get(source_id) or {}
        title = entry.get("title")

        if not anchors:
            messagebox.showinfo(
                "Info",
                f"Ingen ankere funnet for '{source_id}'.\n\n"
                "Tips: Indekser kilden (eller Indekser alle) for å generere ankerliste.",
            )
            return

        def _use(a: str) -> None:
            if which == "from":
                self.var_rel_from_anchor.set(a)
            else:
                self.var_rel_to_anchor.set(a)

        AnchorPickerDialog(self, source_id=source_id, source_title=title, anchors=anchors, on_use=_use)
