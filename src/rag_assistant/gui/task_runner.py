from __future__ import annotations

"""rag_assistant.gui.task_runner

En minimal "kjør i bakgrunnen"-helper for Tkinter.

Hvorfor?
- Indeksering kan ta tid (PDF, mange kilder).
- Hvis vi kjører direkte på UI-tråden, fryser vinduet og oppleves som "crash".

Denne runneren:
- kjører funksjonen i en separat thread
- kaller callbacks tilbake på UI-tråd via `after(0, ...)`
- kan styre en indeterminate Progressbar

Begrensning:
- Én oppgave av gangen (enkelt og robust)
"""

import threading
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class TaskHandle:
    name: str
    thread: threading.Thread


class TkTaskRunner:
    def __init__(self, tk_root: Any, *, progressbar: Any = None, status_var: Any = None) -> None:
        self._root = tk_root
        self._progress = progressbar
        self._status_var = status_var
        self._active: Optional[TaskHandle] = None

    def is_busy(self) -> bool:
        return self._active is not None

    def run(
        self,
        name: str,
        func: Callable[[], Any],
        *,
        on_success: Optional[Callable[[Any], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        start_message: Optional[str] = None,
        done_message: Optional[str] = None,
    ) -> bool:
        """Starter en bakgrunnsoppgave.

        Returnerer False hvis det allerede kjører en oppgave.
        """
        if self._active is not None:
            return False

        def _ui(call: Callable[[], None]) -> None:
            try:
                self._root.after(0, call)
            except Exception:
                # fallback: kall direkte
                call()

        def _start_ui() -> None:
            if self._status_var is not None and start_message:
                try:
                    self._status_var.set(start_message)
                except Exception:
                    pass
            if self._progress is not None:
                try:
                    self._progress.start(8)
                except Exception:
                    pass

        def _stop_ui() -> None:
            if self._progress is not None:
                try:
                    self._progress.stop()
                except Exception:
                    pass
            if self._status_var is not None and done_message:
                try:
                    self._status_var.set(done_message)
                except Exception:
                    pass

        def _worker() -> None:
            try:
                _ui(_start_ui)
                res = func()

                def _ok() -> None:
                    _stop_ui()
                    if on_success:
                        on_success(res)

                _ui(_ok)
            except Exception as e:

                def _err() -> None:
                    _stop_ui()
                    if on_error:
                        on_error(e)

                _ui(_err)
            finally:
                # mark idle
                self._active = None

        t = threading.Thread(target=_worker, daemon=True)
        self._active = TaskHandle(name=name, thread=t)
        t.start()
        return True
