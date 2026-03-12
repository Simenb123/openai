from __future__ import annotations

"""rag_assistant.gui.relation_type_guidance

GUI-hjelp for relasjonstyper *og relasjonsmaler* i Relasjoner-fanen.

Denne logikken er skilt ut fra `relations_tab.py` for å holde filstørrelser nede
og gjøre videre vedlikehold enklere.

D4:
- Relasjonstype-forslag basert på doc_type (Fra/Til)
- Forklaring av valgt relasjonstype
- Hint om typisk retning
- Bytt Fra/Til-knapp

D5:
- Relasjonsmaler (templates) som kan fylle inn:
    * relasjonstype
    * ev. bytte Fra/Til hvis malen matcher i "reverse"
    * standard notat
"""

import tkinter as tk
from tkinter import ttk

from ..relation_suggestions import (
    all_relation_type_keys,
    direction_hint,
    relation_type_description,
    relation_type_label,
    suggest_relation_types,
)
from ..relation_templates import describe_applicable_template, templates_for_pair


class RelationTypeGuidanceMixin:
    """Mixin som gir:
    - forslag til relasjonstyper basert på doc_type (Fra/Til)
    - forklaring av valgt relasjonstype
    - relasjonsmaler (templates)
    - knapp for å bytte Fra/Til
    """

    # Forventede attributter fra host (AdminApp/RelationsTabMixin)
    library: object
    var_rel_from: tk.StringVar
    var_rel_to: tk.StringVar
    var_rel_from_anchor: tk.StringVar
    var_rel_to_anchor: tk.StringVar

    var_rel_type: tk.StringVar
    var_rel_type_desc: tk.StringVar
    var_rel_direction_hint: tk.StringVar

    # D5 templates
    var_rel_template: tk.StringVar
    var_rel_template_desc: tk.StringVar

    cmb_rel_type: ttk.Combobox
    frm_rel_type_buttons: ttk.Frame

    cmb_rel_template: ttk.Combobox
    txt_rel_note: tk.Text

    def _refresh_anchor_dropdowns(self) -> None:  # pragma: no cover
        """Host implementerer."""
        raise NotImplementedError

    def _doc_type_for_source(self, source_id: str) -> str:
        sid = (source_id or "").strip()
        if not sid:
            return "OTHER"
        # `library` er expected å være `kildebibliotek.Library`, men vi duck-typer her.
        try:
            src = self.library.get_source(sid)  # type: ignore[attr-defined]
        except Exception:
            src = None
        if not src:
            return "OTHER"
        dt = getattr(src, "doc_type", None)
        return (dt or "OTHER").strip().upper() or "OTHER"

    def _swap_from_to(self) -> None:
        """Bytter Fra/Til (inkl. ankere)."""
        f = self.var_rel_from.get()
        t = self.var_rel_to.get()
        fa = self.var_rel_from_anchor.get()
        ta = self.var_rel_to_anchor.get()

        self.var_rel_from.set(t)
        self.var_rel_to.set(f)
        self.var_rel_from_anchor.set(ta)
        self.var_rel_to_anchor.set(fa)

        self._refresh_anchor_dropdowns()

    def _set_relation_type(self, rel_type_key: str) -> None:
        key = (rel_type_key or "").strip()
        if not key:
            return
        self.var_rel_type.set(key)
        self._refresh_relation_type_help()

    def _refresh_relation_type_help(self) -> None:
        key = (self.var_rel_type.get() or "").strip() or "RELATES_TO"
        label = relation_type_label(key)
        desc = relation_type_description(key)
        if desc:
            self.var_rel_type_desc.set(f"{label} ({key}) – {desc}")
        else:
            self.var_rel_type_desc.set(f"{label} ({key})")

    # ---------------- Templates (D5) ----------------

    def _refresh_relation_templates(self, from_dt: str, to_dt: str) -> None:
        if not hasattr(self, "cmb_rel_template") or not hasattr(self, "var_rel_template"):
            return

        apps = templates_for_pair(from_dt, to_dt)
        # cache on instance
        setattr(self, "_rel_template_cache", apps)
        values = [describe_applicable_template(a) for a in apps]

        self.cmb_rel_template["values"] = values
        if not values:
            self.var_rel_template.set("")
            self.var_rel_template_desc.set("Ingen maler for valgt Fra/Til")
            return

        # behold valgt hvis mulig
        cur = (self.var_rel_template.get() or "").strip()
        if not cur or cur not in values:
            self.var_rel_template.set(values[0])

        self._refresh_relation_template_help()

    def _refresh_relation_template_help(self) -> None:
        apps = getattr(self, "_rel_template_cache", []) or []
        cur = (self.var_rel_template.get() or "").strip()
        if not cur or not apps:
            return

        # finn valgt index
        idx = None
        for i, app in enumerate(apps):
            if describe_applicable_template(app) == cur:
                idx = i
                break
        if idx is None:
            return

        app = apps[idx]
        t = app.template
        dir_txt = "" if app.direction == "forward" else " (anbefaler å bytte Fra/Til)"
        self.var_rel_template_desc.set(f"{t.description_no}{dir_txt}")

    def _apply_selected_template(self) -> None:
        apps = getattr(self, "_rel_template_cache", []) or []
        cur = (self.var_rel_template.get() or "").strip()
        if not cur or not apps:
            return

        # finn valgt
        chosen = None
        for app in apps:
            if describe_applicable_template(app) == cur:
                chosen = app
                break
        if not chosen:
            return

        # hvis reverse: bytt Fra/Til først
        if chosen.direction == "reverse":
            self._swap_from_to()

        # sett relasjonstype
        self._set_relation_type(chosen.template.relation_type)

        # sett notat (best-effort)
        note = (chosen.template.default_note or "").strip()
        if note and hasattr(self, "txt_rel_note"):
            current = (self.txt_rel_note.get("1.0", tk.END) or "").strip()
            if not current:
                self.txt_rel_note.delete("1.0", tk.END)
                self.txt_rel_note.insert(tk.END, note)
            else:
                # append kun hvis ikke allerede finnes (case-insensitiv)
                if note.lower() not in current.lower():
                    self.txt_rel_note.insert(tk.END, "\n" + note)

        self._refresh_relation_type_help()
        self._refresh_relation_template_help()

    # ---------------- Suggestions (D4) ----------------

    def _refresh_relation_type_suggestions(self) -> None:
        """Oppdaterer forslag/knapper + combobox basert på valgt Fra/Til."""
        from_id = self.var_rel_from.get().strip()
        to_id = self.var_rel_to.get().strip()
        from_dt = self._doc_type_for_source(from_id)
        to_dt = self._doc_type_for_source(to_id)

        suggestions = suggest_relation_types(from_dt, to_dt)
        all_types = all_relation_type_keys()
        ordered = suggestions + [x for x in all_types if x not in suggestions]

        # Oppdater combobox values (behold valgt hvis mulig)
        cur = (self.var_rel_type.get() or "").strip()
        self.cmb_rel_type["values"] = ordered
        if not cur or cur not in ordered:
            self.var_rel_type.set(suggestions[0] if suggestions else "RELATES_TO")

        # Oppdater hint
        hint = direction_hint(from_dt, to_dt) or ""
        self.var_rel_direction_hint.set(hint)

        # Bygg forslag-knapper
        for w in list(self.frm_rel_type_buttons.winfo_children()):
            try:
                w.destroy()
            except Exception:
                pass

        max_btn = 6
        for i, key in enumerate(suggestions[:max_btn]):
            txt = relation_type_label(key)
            ttk.Button(self.frm_rel_type_buttons, text=txt, command=lambda k=key: self._set_relation_type(k)).grid(
                row=0, column=i, padx=(0 if i == 0 else 6, 0)
            )

        # D5: templates
        if hasattr(self, "cmb_rel_template") and hasattr(self, "var_rel_template_desc"):
            self._refresh_relation_templates(from_dt, to_dt)

        self._refresh_relation_type_help()
