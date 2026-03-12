from __future__ import annotations

"""rag_assistant.gui.anchor_picker

En liten dialog for å:
- søke i ankere (fra anker-inventory)
- velge et anker for å bruke i en relasjon
- kopiere ankere til clipboard

Bevisst enkel (Tkinter):
- fungerer i Windows/PyCharm
- håndterer store ankerlister (begrenset visning)

Testing:
- GUI er vanskelig å enhetsteste uten display.
- Vi tester derfor den rene filterfunksjonen `filter_anchors` i pytest.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, List, Optional


def filter_anchors(anchors: List[str], query: str, *, max_results: int = 2000) -> List[str]:
    """Filtrer ankere med best-effort søk.

    - Normaliserer query ved å fjerne whitespace og gjøre upper()
    - Match: substring (case-insensitiv)

    Returnerer maks `max_results`.
    """
    if not anchors:
        return []
    q = (query or "").strip()
    if not q:
        return anchors[:max_results]

    qn = "".join(q.split()).upper()
    out: List[str] = []
    for a in anchors:
        an = "".join(str(a).split()).upper()
        if qn in an:
            out.append(str(a))
            if len(out) >= max_results:
                break
    return out


class AnchorPickerDialog(tk.Toplevel):
    """Dialog for å vise/velge ankere.

    Hvis `on_use` er satt, får dialogen knapp "Bruk valgt" og dobbeltklikk bruker anker.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        source_id: str,
        source_title: Optional[str],
        anchors: List[str],
        on_use: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.title(f"Ankere – {source_id}")
        self.geometry("520x520")
        self.transient(parent)
        self.grab_set()

        self._source_id = source_id
        self._source_title = source_title
        self._anchors_all = list(anchors)
        self._on_use = on_use

        self._var_query = tk.StringVar()
        self._var_info = tk.StringVar(value="")

        self._build_ui()
        self._refresh()

        self._entry_query.focus_set()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=10)

        title = self._source_title or self._source_id
        ttk.Label(header, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Label(header, text=f"Kilde-ID: {self._source_id}").pack(anchor="w")

        search = ttk.Frame(self)
        search.pack(fill=tk.X, padx=10)
        ttk.Label(search, text="Søk:").pack(side=tk.LEFT)
        self._entry_query = ttk.Entry(search, textvariable=self._var_query)
        self._entry_query.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self._entry_query.bind("<KeyRelease>", lambda _e: self._refresh())
        self._entry_query.bind("<Return>", lambda _e: self._use_selected())

        ttk.Label(self, textvariable=self._var_info).pack(anchor="w", padx=10, pady=(6, 0))

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self._list = tk.Listbox(body, height=18)
        self._list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._list.bind("<Double-Button-1>", lambda _e: self._use_selected())

        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self._list.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._list.configure(yscrollcommand=scroll.set)

        buttons = ttk.Frame(self)
        buttons.pack(fill=tk.X, padx=10, pady=(0, 10))

        if self._on_use is not None:
            ttk.Button(buttons, text="Bruk valgt", command=self._use_selected).pack(side=tk.LEFT)

        ttk.Button(buttons, text="Kopier valgt", command=self._copy_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(buttons, text="Kopier alle", command=self._copy_all).pack(side=tk.LEFT, padx=(6, 0))

        ttk.Button(buttons, text="Lukk", command=self.destroy).pack(side=tk.RIGHT)

    def _refresh(self) -> None:
        q = self._var_query.get()
        filtered = filter_anchors(self._anchors_all, q)

        self._list.delete(0, tk.END)
        for a in filtered:
            self._list.insert(tk.END, a)

        total = len(self._anchors_all)
        shown = len(filtered)
        if q.strip():
            self._var_info.set(f"Viser {shown} av {total} (filter: '{q.strip()}')")
        else:
            self._var_info.set(f"Viser {shown} av {total}")

        if shown > 0:
            self._list.selection_clear(0, tk.END)
            self._list.selection_set(0)

    def _get_selected_anchor(self) -> Optional[str]:
        sel = self._list.curselection()
        if not sel:
            return None
        idx = int(sel[0])
        try:
            return str(self._list.get(idx))
        except Exception:
            return None

    def _use_selected(self) -> None:
        a = self._get_selected_anchor()
        if not a:
            return
        if self._on_use is not None:
            try:
                self._on_use(a)
            finally:
                self.destroy()

    def _copy_selected(self) -> None:
        a = self._get_selected_anchor()
        if not a:
            return
        self.clipboard_clear()
        self.clipboard_append(a)

    def _copy_all(self) -> None:
        all_text = "\n".join(self._anchors_all)
        self.clipboard_clear()
        self.clipboard_append(all_text)
