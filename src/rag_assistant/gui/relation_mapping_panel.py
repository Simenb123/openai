from __future__ import annotations

"""rag_assistant.gui.relation_mapping_panel

D6: Kartleggingspanel for relasjonsbygging på ankernivå.
D8: Brukerflyt/effektivitet:
  - Vis eksisterende koblinger for valgt fra-anker
  - "Neste umappede"/"Forrige umappede" navigasjon
  - "Kun umappede"-filter
  - Fremdrift: hvor mange fra-ankere som er mappet

Mål:
- Gjøre det raskt å bygge relasjoner paragraf-for-paragraf (og ledd/bokstav)
  mellom f.eks. Revisorloven (RL) og Revisorforskriften (RF).
- Vise innholdet i ankere direkte i GUI slik at du kan koble korrekt.

Panelet er generisk:
- Bruker "Fra" og "Til" som allerede er valgt i Relasjoner-skjemaet.
- Henter ankerlister fra `kildebibliotek.anchors.json` (anchor_inventory)
- Leser anker-tekst fra kildefiler (uten å kreve indeksering)
"""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable, Dict, List, Optional

from ..anchor_texts import AnchorTextCache, preview_text
from ..anchor_validation import anchors_for_source
from ..kildebibliotek import Relation
from ..relation_mapping import (
    apply_suggestions_to_ordered_list,
    group_relations_by_from_anchor,
    suggest_target_anchors,
)


class RelationMappingPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        library: Any,
        library_path: Path,
        anchor_inventory: Dict[str, Any],
        get_from_id: Callable[[], str],
        get_to_id: Callable[[], str],
        get_relation_type: Callable[[], str],
        get_note: Callable[[], str],
        on_add_relations: Callable[[List[Relation]], None],
        on_remove_relations: Callable[[List[Relation]], None] | None,
        on_status: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._library = library
        self._library_path = library_path
        self._anchor_inventory = anchor_inventory

        self._get_from_id = get_from_id
        self._get_to_id = get_to_id
        self._get_relation_type = get_relation_type
        self._get_note = get_note
        self._on_add_relations = on_add_relations
        self._on_remove_relations = on_remove_relations
        self._on_status = on_status

        self._text_cache = AnchorTextCache(library=library, base_dir=library_path.parent)

        self._from_anchors_all: List[str] = []
        self._to_anchors_all: List[str] = []

        # synlig mapping mellom listbox-indeks -> anker (fordi vi viser ✓ prefiks i UI)
        self._from_visible_anchors: List[str] = []

        # D8: mapping state
        self._existing_by_from_anchor: Dict[str, List[Relation]] = {}
        self._mapped_from_anchors: set[str] = set()
        self._pair_rel_count: int = 0

        self._existing_visible_rels: List[Relation] = []

        self._var_from_filter = tk.StringVar(value="")
        self._var_to_filter = tk.StringVar(value="")
        self._var_info = tk.StringVar(value="")
        self._var_existing_info = tk.StringVar(value="")
        self._var_only_unmapped = tk.BooleanVar(value=False)

        self._build_ui()
        self.refresh_lists()

    def set_anchor_inventory(self, inv: Dict[str, Any]) -> None:
        self._anchor_inventory = inv
        self.refresh_lists()

    # ---------------- UI ----------------

    def _build_ui(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=8, pady=(8, 6))

        ttk.Button(top, text="Oppdater", command=self.refresh_lists).pack(side=tk.LEFT)
        ttk.Button(top, text="Auto-velg kandidater", command=self._auto_select_candidates).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        ttk.Checkbutton(top, text="Kun umappede", variable=self._var_only_unmapped, command=self._on_toggle_only_unmapped).pack(
            side=tk.LEFT, padx=(10, 0)
        )

        ttk.Button(top, text="Legg til valgte", command=self._add_selected).pack(side=tk.RIGHT)
        ttk.Button(top, text="Legg til & neste", command=self._add_and_next).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Label(top, textvariable=self._var_info).pack(side=tk.RIGHT, padx=(10, 10))

        # 3 kolonner: Fra-ankere | Til-ankere | Preview + eksisterende
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.columnconfigure(2, weight=2)
        body.rowconfigure(2, weight=1)

        ttk.Label(body, text="Fra-ankere").grid(row=0, column=0, sticky="w")
        ttk.Label(body, text="Til-ankere (multi-select)").grid(row=0, column=1, sticky="w")
        ttk.Label(body, text="Innhold + koblinger").grid(row=0, column=2, sticky="w")

        # Filter
        ttk.Entry(body, textvariable=self._var_from_filter).grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Entry(body, textvariable=self._var_to_filter).grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ttk.Label(body, text="(Velg anker(e) for å se tekst)").grid(row=1, column=2, sticky="w")

        self._var_from_filter.trace_add("write", lambda *_: self._refresh_listboxes(preserve=True))
        self._var_to_filter.trace_add("write", lambda *_: self._refresh_listboxes(preserve=True))

        # From list
        self._lst_from = tk.Listbox(body, exportselection=False)
        self._lst_from.grid(row=2, column=0, sticky="nsew", padx=(0, 6))
        self._lst_from.bind("<<ListboxSelect>>", lambda _e: self._on_select_from())

        # To list (multi)
        self._lst_to = tk.Listbox(body, selectmode=tk.EXTENDED, exportselection=False)
        self._lst_to.grid(row=2, column=1, sticky="nsew", padx=(0, 6))
        self._lst_to.bind("<<ListboxSelect>>", lambda _e: self._on_select_to())

        # Preview + existing
        prev = ttk.Frame(body)
        prev.grid(row=2, column=2, sticky="nsew")
        prev.columnconfigure(0, weight=1)
        prev.rowconfigure(1, weight=1)
        prev.rowconfigure(3, weight=1)
        prev.rowconfigure(5, weight=1)

        ttk.Label(prev, text="Fra (anker):").grid(row=0, column=0, sticky="w")
        self._txt_from = tk.Text(prev, height=7)
        self._txt_from.grid(row=1, column=0, sticky="nsew")

        ttk.Label(prev, text="Til (anker):").grid(row=2, column=0, sticky="w", pady=(6, 0))
        self._txt_to = tk.Text(prev, height=7)
        self._txt_to.grid(row=3, column=0, sticky="nsew")

        ttk.Label(prev, text="Eksisterende koblinger (for valgt fra-anker):").grid(row=4, column=0, sticky="w", pady=(8, 0))
        self._lst_existing = tk.Listbox(prev, selectmode=tk.EXTENDED, exportselection=False, height=6)
        self._lst_existing.grid(row=5, column=0, sticky="nsew")
        self._lst_existing.bind("<<ListboxSelect>>", lambda _e: self._on_select_existing())

        ex_btns = ttk.Frame(prev)
        ex_btns.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self._btn_remove_existing = ttk.Button(ex_btns, text="Fjern valgte", command=self._remove_existing_selected)
        self._btn_remove_existing.pack(side=tk.LEFT)
        ttk.Label(ex_btns, textvariable=self._var_existing_info).pack(side=tk.RIGHT)

        # disable remove if callback missing
        if self._on_remove_relations is None:
            try:
                self._btn_remove_existing.configure(state="disabled")
            except Exception:
                pass

        nav = ttk.Frame(self)
        nav.pack(fill=tk.X, padx=8, pady=(0, 8))
        ttk.Button(nav, text="Forrige fra-anker", command=lambda: self._move_from(-1)).pack(side=tk.LEFT)
        ttk.Button(nav, text="Neste fra-anker", command=lambda: self._move_from(+1)).pack(side=tk.LEFT, padx=6)
        ttk.Button(nav, text="Forrige umappede", command=lambda: self._move_unmapped(-1)).pack(side=tk.LEFT, padx=(16, 0))
        ttk.Button(nav, text="Neste umappede", command=lambda: self._move_unmapped(+1)).pack(side=tk.LEFT, padx=6)

    # ---------------- public refresh hooks ----------------

    def refresh_relation_state(self) -> None:
        """Kalles når bibliotekets relasjoner endres (D8)."""
        selected = self._selected_from_anchor()
        self._recompute_mapping_state()
        self._update_info()
        self._refresh_listboxes(preserve=True, preserve_from_anchor=selected)
        self._refresh_existing_list_for_selected()

    # ---------------- data refresh ----------------

    def refresh_lists(self) -> None:
        """Henter ankerlister basert på valgt Fra/Til."""
        from_id = self._get_from_id().strip()
        to_id = self._get_to_id().strip()

        # Reset cache hvis kilde endres
        self._text_cache.invalidate(from_id)
        self._text_cache.invalidate(to_id)

        # Primært: ankerliste fra anchor_inventory (generert ved indeksering)
        self._from_anchors_all = anchors_for_source(self._anchor_inventory, from_id) if from_id else []
        self._to_anchors_all = anchors_for_source(self._anchor_inventory, to_id) if to_id else []

        # Best-effort fallback: hvis ankerliste mangler, bygg direkte fra tekst
        if from_id and not self._from_anchors_all:
            amap = self._text_cache.get(from_id)
            if amap:
                self._from_anchors_all = sorted(amap.keys())
                self._on_status("Kartlegging: Fra-ankere hentet direkte fra tekst (ankerlisten mangler/er tom)")

        if to_id and not self._to_anchors_all:
            amap = self._text_cache.get(to_id)
            if amap:
                self._to_anchors_all = sorted(amap.keys())
                self._on_status("Kartlegging: Til-ankere hentet direkte fra tekst (ankerlisten mangler/er tom)")

        # D8: mapping state før vi tegner listene
        self._recompute_mapping_state()
        self._refresh_listboxes(preserve=False)
        self._update_info()
        self._refresh_existing_list_for_selected()

    def _recompute_mapping_state(self) -> None:
        from_id = self._get_from_id().strip()
        to_id = self._get_to_id().strip()

        rels = list(getattr(self._library, "relations", []) or [])
        self._pair_rel_count = 0
        try:
            for r in rels:
                if r.from_id == from_id and r.to_id == to_id:
                    self._pair_rel_count += 1
        except Exception:
            self._pair_rel_count = 0

        self._existing_by_from_anchor = group_relations_by_from_anchor(rels, from_id, to_id)
        self._mapped_from_anchors = set(self._existing_by_from_anchor.keys())

    def _on_toggle_only_unmapped(self) -> None:
        self._refresh_listboxes(preserve=True)
        self._update_info()

    def _refresh_listboxes(self, *, preserve: bool, preserve_from_anchor: Optional[str] = None) -> None:
        # Preserve selection by anchor if requested
        prev_from = preserve_from_anchor or (self._selected_from_anchor() if preserve else None)

        f = self._var_from_filter.get().strip().upper()
        t = self._var_to_filter.get().strip().upper()

        from_vals = self._from_anchors_all
        to_vals = self._to_anchors_all

        if f:
            from_vals = [a for a in from_vals if f in a.upper()]
        if self._var_only_unmapped.get():
            from_vals = [a for a in from_vals if a not in self._mapped_from_anchors]

        if t:
            to_vals = [a for a in to_vals if t in a.upper()]

        # From list with ✓ prefix
        self._lst_from.delete(0, tk.END)
        self._from_visible_anchors = []
        for a in from_vals[:5000]:
            if a in self._mapped_from_anchors:
                n = len(self._existing_by_from_anchor.get(a, []))
                disp = f"✓ {a} ({n})"
            else:
                disp = f"  {a}"
            self._from_visible_anchors.append(a)
            self._lst_from.insert(tk.END, disp)

        # To list (plain)
        self._lst_to.delete(0, tk.END)
        for a in to_vals[:5000]:
            self._lst_to.insert(tk.END, a)

        # Restore from selection if possible
        if prev_from and prev_from in self._from_visible_anchors:
            idx = self._from_visible_anchors.index(prev_from)
            self._lst_from.selection_clear(0, tk.END)
            self._lst_from.selection_set(idx)
            self._lst_from.see(idx)
            self._on_select_from()
        else:
            # auto-select første fra-anker hvis ingenting valgt
            if self._lst_from.size() > 0 and not self._lst_from.curselection():
                self._lst_from.selection_set(0)
                self._on_select_from()

    def _update_info(self) -> None:
        n_from = len(self._from_anchors_all)
        n_to = len(self._to_anchors_all)
        mapped = 0
        if n_from:
            mapped = len([a for a in self._from_anchors_all if a in self._mapped_from_anchors])
        self._var_info.set(f"Fra:{n_from} (mappet {mapped}/{n_from}) • Til:{n_to} • Rel:{self._pair_rel_count}")

    # ---------------- selection ----------------

    def _selected_from_anchor(self) -> Optional[str]:
        sel = self._lst_from.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx < 0 or idx >= len(self._from_visible_anchors):
            return None
        return self._from_visible_anchors[idx]

    def _selected_to_anchors(self) -> List[str]:
        sel = self._lst_to.curselection()
        return [self._lst_to.get(i) for i in sel]

    def _on_select_from(self) -> None:
        a = self._selected_from_anchor()
        self._txt_from.delete("1.0", tk.END)
        if not a:
            self._clear_existing_list()
            return

        from_id = self._get_from_id().strip()
        amap = self._text_cache.get(from_id)
        self._txt_from.insert(tk.END, preview_text(amap.get(a, "")))

        # D8: update existing relations list + sync selection in to-list
        self._refresh_existing_list_for_selected()

    def _on_select_to(self) -> None:
        # Vis preview for første valgte (hvis flere)
        sel = self._selected_to_anchors()
        self._txt_to.delete("1.0", tk.END)
        if not sel:
            return
        a = sel[0]
        to_id = self._get_to_id().strip()
        amap = self._text_cache.get(to_id)
        self._txt_to.insert(tk.END, preview_text(amap.get(a, "")))

    def _on_select_existing(self) -> None:
        """Når brukeren klikker en eksisterende kobling: synk til-lista og preview."""
        sel = self._lst_existing.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < 0 or idx >= len(self._existing_visible_rels):
            return
        rel = self._existing_visible_rels[idx]
        if not rel.to_anchor:
            return

        # Velg samme til-anker i til-lista (hvis synlig)
        try:
            self._select_to_anchors([rel.to_anchor], clear=True)
        except Exception:
            pass

    # ---------------- existing relations UI ----------------

    def _clear_existing_list(self) -> None:
        self._existing_visible_rels = []
        self._lst_existing.delete(0, tk.END)
        self._var_existing_info.set("")

    def _refresh_existing_list_for_selected(self) -> None:
        fa = self._selected_from_anchor()
        if not fa:
            self._clear_existing_list()
            return

        rels = list(self._existing_by_from_anchor.get(fa, []))
        self._existing_visible_rels = rels
        self._lst_existing.delete(0, tk.END)

        for r in rels[:5000]:
            ta = r.to_anchor or ""
            rt = r.relation_type
            self._lst_existing.insert(tk.END, f"{ta}  [{rt}]")

        self._var_existing_info.set(f"{len(rels)} stk")

        # Synkroniser til-lista slik at eksisterende koblinger blir synlige i multi-select
        to_anchors = [r.to_anchor for r in rels if r.to_anchor]
        if to_anchors:
            self._select_to_anchors(to_anchors, clear=True)
        else:
            # ingen eksisterende: ikke auto-clear, men vi kan vise tom preview
            pass

    def _remove_existing_selected(self) -> None:
        if self._on_remove_relations is None:
            return
        sel = self._lst_existing.curselection()
        if not sel:
            return

        rels: List[Relation] = []
        for i in sel:
            if 0 <= i < len(self._existing_visible_rels):
                rels.append(self._existing_visible_rels[i])

        if not rels:
            return

        if not messagebox.askyesno("Fjern", f"Fjerne {len(rels)} kobling(er)?"):
            return

        self._on_remove_relations(rels)
        self._on_status(f"Fjernet {len(rels)} kobling(er)")

    def _select_to_anchors(self, anchors: List[str], *, clear: bool) -> None:
        """Velg en liste av til-ankere i til-lista (tar hensyn til filter).

        Hvis noen ankere ikke er synlige (pga filter), informerer vi i status.
        """
        if clear:
            self._lst_to.selection_clear(0, tk.END)

        visible = [self._lst_to.get(i) for i in range(self._lst_to.size())]
        vset = set(visible)
        wanted = [a for a in anchors if a in vset]

        if not wanted:
            # Ikke spam status hvis filter er tomt og bare ingen eksisterer.
            if anchors and self._var_to_filter.get().strip():
                self._on_status("Eksisterende koblinger finnes, men er skjult av filter i Til-lista")
            return

        # Multi-select: velg alle
        for i, a in enumerate(visible):
            if a in wanted:
                self._lst_to.selection_set(i)

        # Oppdater preview
        self._on_select_to()

    # ---------------- actions ----------------

    def _auto_select_candidates(self) -> None:
        from_anchor = self._selected_from_anchor()
        if not from_anchor:
            return
        if self._lst_to.size() == 0:
            return

        # Kandidater basert på hele to-listen (ikke filtrert)
        suggestions = suggest_target_anchors(from_anchor, self._to_anchors_all)
        ordered = apply_suggestions_to_ordered_list(self._to_anchors_all, suggestions)
        if not ordered:
            self._on_status("Ingen kandidater funnet (prøv filter eller manuelt valg)")
            return

        # Clear og velg de som er synlige i listbox (tar hensyn til filter)
        self._lst_to.selection_clear(0, tk.END)

        visible = [self._lst_to.get(i) for i in range(self._lst_to.size())]
        visible_set = set(visible)
        picked = [a for a in ordered if a in visible_set]
        if not picked:
            # hvis filter skjuler kandidater, gi hint
            self._on_status("Kandidater finnes, men er skjult av filter. Tøm filter for å auto-velge.")
            return

        # Velg opptil 20 i UI (så den ikke blir for 'sticky')
        max_ui = 20
        count = 0
        for i, a in enumerate(visible):
            if a in picked:
                self._lst_to.selection_set(i)
                count += 1
                if count >= max_ui:
                    break

        self._on_status(f"Auto-valgte {count} kandidater")
        self._on_select_to()

    def _build_relations_from_selection(self) -> List[Relation]:
        from_id = self._get_from_id().strip()
        to_id = self._get_to_id().strip()
        if not from_id or not to_id:
            messagebox.showinfo("Info", "Velg både Fra og Til først")
            return []

        from_anchor = self._selected_from_anchor()
        to_anchors = self._selected_to_anchors()

        if not from_anchor:
            messagebox.showinfo("Info", "Velg et Fra-anker")
            return []
        if not to_anchors:
            messagebox.showinfo("Info", "Velg minst ett Til-anker")
            return []

        rel_type = (self._get_relation_type() or "RELATES_TO").strip() or "RELATES_TO"
        note = (self._get_note() or "").strip() or None

        rels: List[Relation] = []
        for ta in to_anchors:
            rels.append(
                Relation(
                    from_id=from_id,
                    to_id=to_id,
                    relation_type=rel_type,
                    from_anchor=from_anchor,
                    to_anchor=ta,
                    note=note,
                )
            )
        return rels

    def _add_selected(self) -> None:
        rels = self._build_relations_from_selection()
        if not rels:
            return
        self._on_add_relations(rels)
        self._on_status(f"La til/oppdaterte {len(rels)} relasjoner (kartlegging)")

    def _add_and_next(self) -> None:
        rels = self._build_relations_from_selection()
        if not rels:
            return
        self._on_add_relations(rels)
        self._on_status(f"La til/oppdaterte {len(rels)} relasjoner (kartlegging)")

        # clear to-selection for neste runde
        self._lst_to.selection_clear(0, tk.END)
        # D8: hopp til neste umappede for effektiv flyt
        self._move_unmapped(+1)

    def _move_from(self, delta: int) -> None:
        if self._lst_from.size() == 0:
            return
        sel = self._lst_from.curselection()
        cur = sel[0] if sel else 0
        nxt = max(0, min(self._lst_from.size() - 1, cur + int(delta)))
        self._lst_from.selection_clear(0, tk.END)
        self._lst_from.selection_set(nxt)
        self._lst_from.see(nxt)
        self._on_select_from()

    def _move_unmapped(self, delta: int) -> None:
        """Flytt til neste/forrige umappede fra-anker i *synlig* liste."""
        if self._lst_from.size() == 0:
            return

        sel = self._lst_from.curselection()
        cur = sel[0] if sel else (-1 if delta > 0 else self._lst_from.size())

        if delta > 0:
            rng = range(cur + 1, self._lst_from.size())
        else:
            rng = range(cur - 1, -1, -1)

        for i in rng:
            if i < 0 or i >= len(self._from_visible_anchors):
                continue
            a = self._from_visible_anchors[i]
            if a not in self._mapped_from_anchors:
                self._lst_from.selection_clear(0, tk.END)
                self._lst_from.selection_set(i)
                self._lst_from.see(i)
                self._on_select_from()
                return

        self._on_status("Fant ingen flere umappede ankere i listen")
