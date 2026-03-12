from __future__ import annotations

"""Entry-point wrapper for Tkinter Admin GUI.

Implementasjonen ligger i `rag_assistant.gui.admin_app` for å holde filstørrelser nede
og gjøre GUI-koden mer vedlikeholdbar.
"""

from pathlib import Path
from typing import Optional

from .gui.admin_app import AdminApp

__all__ = ["AdminApp", "main"]


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Tkinter GUI for å administrere kildebibliotek")
    parser.add_argument("library_path", nargs="?", default="kildebibliotek.json")
    args = parser.parse_args(argv)

    lib_path = Path(args.library_path)
    app = AdminApp(lib_path)
    app.mainloop()
    return 0
