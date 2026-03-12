from __future__ import annotations

"""rag_assistant.gui.anchor_tree_panel

En gjenbrukbar Tkinter-komponent som viser ankere som et hierarkisk tre:

- Juridisk: § -> ledd -> bokstav
- Standard: P -> underpunkt (P1.2) og A-ankere

Bruk:
- Relasjoner-fanen bruker to paneler (Fra / Til) for å gjøre relasjonsbygging raskt.

Dette er UI-kode (Tkinter). Selve trelogikken ligger i `rag_assistant.anchor_tree_model`
for å kunne testes uten GUI.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional

from ..anchor_tree_model import build_tree_edges, filter_anchors_with_context, roots


class AnchorTreePanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str,
        get_source_id: Callable[[], str],
        get_anchors_for_source: Callable[[str], List[str]],
        on_use_anchor: Callable[[str], None],
        max_display_nodes: int = 10000,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._get_source_id = get_source_id
        self._get_anchors_for_source = get_anchors_for_source
        self._on_use_anchor = on_use_anchor
        self._max_display_nodes = max_display_nodes

        self._anchors_all: List[str] = []
        self._edges: Dict[Optional[str], List[str]] = {}
        self._iid_to_anchor: Dict[str, str] = {}

        self._var_query = tk.StringVar(value="")
        self._var_info = tk.StringVar(value="")

        self._build_ui()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=8, pady=(8, 4))

        ttk.Label(header, text=self._title, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, textvariable=self._var_info).pack(side=tk.RIGHT)

        search = ttk.Frame(self)
        search.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Label(search, text="Filter:").pack(side=tk.LEFT)
        ent = ttk.Entry(search, textvariable=self._var_query)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        ent.bind("<KeyRelease>", lambda _e: self.refresh_tree())

        btns = ttk.Frame(self)
        btns.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(btns, text="Bruk valgt", command=self._use_selected).pack(side=tk.LEFT)
        ttk.Button(btns, text="Kopier valgt", command=self._copy_selected).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(btns, text="Utvid alle", command=self._expand_all).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Kollaps", command=self._collapse_all).pack(side=tk.RIGHT, padx=(0, 6))

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._tree = ttk.Treeview(body, columns=("anchor",), show="tree", height=10)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._tree.bind("<Double-Button-1>", lambda _e: self._use_selected())
        self._tree.bind("<Return>", lambda _e: self._use_selected())

        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=self._tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.configure(yscrollcommand=scroll.set)

    def set_query(self, q: str) -> None:
        self._var_query.set(q or "")
        self.refresh_tree()

    def refresh_source(self) -> None:
        """Oppdaterer internt anker-sett basert på valgt source_id."""
        sid = (self._get_source_id() or "").strip()
        self._anchors_all = self._get_anchors_for_source(sid) if sid else []
        self._var_info.set(f"{len(self._anchors_all)} ankere" if self._anchors_all else "0 ankere")
        self.refresh_tree()

    def refresh_tree(self) -> None:
        """Rebuild tree basert på ankerliste + filter."""
        self._tree.delete(*self._tree.get_children())
        self._iid_to_anchor.clear()

        if not self._anchors_all:
            return

        q = self._var_query.get()
        nodes = filter_anchors_with_context(self._anchors_all, q)
        if len(nodes) > self._max_display_nodes:
            nodes = nodes[: self._max_display_nodes]

        self._edges = build_tree_edges(nodes)

        # bygg tre
        for r in roots(self._edges):
            self._insert_node(parent_iid="", anchor=r)

        # ved filter: utvid litt for å vise treff
        if q.strip():
            self._expand_all(max_nodes=600)

    def _insert_node(self, parent_iid: str, anchor: str) -> None:
        iid = f"n{len(self._iid_to_anchor)}"
        self._iid_to_anchor[iid] = anchor
        self._tree.insert(parent_iid, tk.END, iid=iid, text=anchor)

        for child in self._edges.get(anchor, []):
            if child == anchor:
                continue
            self._insert_node(iid, child)

    def _selected_anchor(self) -> Optional[str]:
        sel = self._tree.selection()
        if not sel:
            return None
        iid = sel[0]
        return self._iid_to_anchor.get(iid)

    def _use_selected(self) -> None:
        a = self._selected_anchor()
        if not a:
            return
        self._on_use_anchor(a)

    def _copy_selected(self) -> None:
        a = self._selected_anchor()
        if not a:
            return
        self.clipboard_clear()
        self.clipboard_append(a)

    def _expand_all(self, *, max_nodes: int = 2000) -> None:
        # best-effort, ikke prøv å utvide enorme trær fullt ut
        count = 0
        stack = list(self._tree.get_children(""))

        while stack and count < max_nodes:
            iid = stack.pop()
            self._tree.item(iid, open=True)
            children = list(self._tree.get_children(iid))
            stack.extend(children)
            count += 1

    def _collapse_all(self) -> None:
        stack = list(self._tree.get_children(""))

        while stack:
            iid = stack.pop()
            self._tree.item(iid, open=False)
            stack.extend(list(self._tree.get_children(iid)))
