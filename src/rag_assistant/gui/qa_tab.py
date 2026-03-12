from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from ..env_loader import load_env
from ..qa_service import QueryOutcome, run_golden_suite, run_query


class QATabMixin:
    """GUI-tab for å teste retrieval/QA uten å hoppe ut i terminal.

    Fokus:
    - enkelt å prøve ut spørsmål raskt
    - både context-only og LLM-svar
    - enkel kjøring av golden eval
    - bakgrunnsoppgaver slik at GUI ikke fryser
    """

    library_path: Path
    status: tk.StringVar

    def _build_qa_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        # Controls
        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        controls.columnconfigure(1, weight=1)
        controls.columnconfigure(3, weight=1)

        self.var_qa_question = tk.StringVar()
        self.var_qa_k = tk.IntVar(value=5)
        self.var_qa_relations = tk.BooleanVar(value=True)
        self.var_qa_golden = tk.StringVar(value="golden/golden_isa230_pilot.json")

        ttk.Label(controls, text="Spørsmål:").grid(row=0, column=0, sticky="w")
        ent_q = ttk.Entry(controls, textvariable=self.var_qa_question)
        ent_q.grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ent_q.bind("<Return>", lambda _e: self._qa_retrieve())

        ttk.Label(controls, text="Top-k:").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(controls, from_=1, to=20, textvariable=self.var_qa_k, width=5).grid(row=0, column=3, sticky="w")

        ttk.Checkbutton(controls, text="Bruk relasjoner", variable=self.var_qa_relations).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Hent kontekst", command=self._qa_retrieve).grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Spør med LLM", command=self._qa_ask_llm).grid(row=1, column=1, sticky="e", pady=(8, 0))
        ttk.Button(controls, text="Tøm", command=self._qa_clear).grid(row=1, column=2, sticky="w", pady=(8, 0))
        ttk.Button(controls, text="Kopier svar", command=self._qa_copy_answer).grid(row=1, column=3, sticky="e", pady=(8, 0))

        golden = ttk.Frame(parent)
        golden.grid(row=1, column=0, sticky="ew", padx=10)
        golden.columnconfigure(1, weight=1)
        ttk.Label(golden, text="Golden-fil:").grid(row=0, column=0, sticky="w")
        ttk.Entry(golden, textvariable=self.var_qa_golden).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Button(golden, text="Kjør golden eval", command=self._qa_run_golden).grid(row=0, column=2, sticky="e")

        # Output
        nb = ttk.Notebook(parent)
        nb.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)

        tab_answer = ttk.Frame(nb)
        tab_context = ttk.Frame(nb)
        tab_sources = ttk.Frame(nb)
        tab_report = ttk.Frame(nb)
        nb.add(tab_answer, text="Svar")
        nb.add(tab_context, text="Kontekst")
        nb.add(tab_sources, text="Kilder")
        nb.add(tab_report, text="Rapport")

        for tab in (tab_answer, tab_context, tab_sources, tab_report):
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

        self.txt_qa_answer = tk.Text(tab_answer, wrap="word")
        self.txt_qa_answer.grid(row=0, column=0, sticky="nsew")

        self.txt_qa_context = tk.Text(tab_context, wrap="word")
        self.txt_qa_context.grid(row=0, column=0, sticky="nsew")

        self.txt_qa_sources = tk.Text(tab_sources, wrap="word")
        self.txt_qa_sources.grid(row=0, column=0, sticky="nsew")

        self.txt_qa_report = tk.Text(tab_report, wrap="word")
        self.txt_qa_report.grid(row=0, column=0, sticky="nsew")

    # ---- helpers ----

    def _qa_clear(self) -> None:
        for widget in (self.txt_qa_answer, self.txt_qa_context, self.txt_qa_sources, self.txt_qa_report):
            widget.delete("1.0", tk.END)

    def _qa_write_outcome(self, outcome: QueryOutcome) -> None:
        self.txt_qa_answer.delete("1.0", tk.END)
        self.txt_qa_context.delete("1.0", tk.END)
        self.txt_qa_sources.delete("1.0", tk.END)

        self.txt_qa_answer.insert(tk.END, outcome.answer or "[Ingen LLM-svar – retrieval/context-only]")
        self.txt_qa_context.insert(tk.END, outcome.context or "[Tom kontekst]")
        self.txt_qa_sources.insert(tk.END, outcome.sources_text or "[Ingen kilder]")

    def _qa_copy_answer(self) -> None:
        txt = self.txt_qa_answer.get("1.0", tk.END).strip()
        if not txt:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(txt)
            self.status.set("Kopierte svar til utklippstavlen")
        except Exception:
            pass

    def _qa_validate_question(self) -> str | None:
        q = (self.var_qa_question.get() or "").strip()
        if not q:
            messagebox.showinfo("Info", "Skriv et spørsmål først")
            return None
        return q

    def _qa_retrieve(self) -> None:
        q = self._qa_validate_question()
        if not q:
            return

        def _work() -> QueryOutcome:
            return run_query(
                q,
                library_path=self.library_path,
                n_results=max(1, int(self.var_qa_k.get() or 5)),
                expand_relations=bool(self.var_qa_relations.get()),
                use_llm=False,
            )

        def _ok(res: QueryOutcome) -> None:
            self._qa_write_outcome(res)
            self.status.set("Hentet kontekst")

        def _err(e: Exception) -> None:
            messagebox.showerror("Feil", f"Retrieval feilet: {e}")

        if hasattr(self, "run_task"):
            self.run_task(
                "qa_retrieve",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message="Henter kontekst…",
                done_message="Kontekst ferdig",
            )
        else:
            try:
                _ok(_work())
            except Exception as e:
                _err(e)

    def _qa_ask_llm(self) -> None:
        q = self._qa_validate_question()
        if not q:
            return
        load_env()
        if not os.environ.get("OPENAI_API_KEY"):
            messagebox.showinfo("Mangler OPENAI_API_KEY", "OPENAI_API_KEY mangler. Legg den i .env i prosjektroten.")
            return

        def _work() -> QueryOutcome:
            return run_query(
                q,
                library_path=self.library_path,
                n_results=max(1, int(self.var_qa_k.get() or 5)),
                expand_relations=bool(self.var_qa_relations.get()),
                use_llm=True,
            )

        def _ok(res: QueryOutcome) -> None:
            self._qa_write_outcome(res)
            self.status.set("LLM-svar klart")

        def _err(e: Exception) -> None:
            messagebox.showerror("Feil", f"Spør med LLM feilet: {e}")

        if hasattr(self, "run_task"):
            self.run_task(
                "qa_llm",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message="Spør modellen…",
                done_message="Svar ferdig",
            )
        else:
            try:
                _ok(_work())
            except Exception as e:
                _err(e)

    def _qa_run_golden(self) -> None:
        golden_path = (self.var_qa_golden.get() or "").strip()
        if not golden_path:
            messagebox.showinfo("Info", "Velg en golden-fil først")
            return

        def _work() -> tuple[dict, Path]:
            out = Path("reports") / "gui_golden_report.json"
            res = run_golden_suite(
                golden_path=golden_path,
                report_path=out,
                library_path=self.library_path,
                n_results=max(1, int(self.var_qa_k.get() or 5)),
                expand_relations=bool(self.var_qa_relations.get()),
            )
            return res.report, res.report_path

        def _ok(res: tuple[dict, Path]) -> None:
            report, path = res
            self.txt_qa_report.delete("1.0", tk.END)
            self.txt_qa_report.insert(tk.END, f"Rapport: {path}\n\n")
            self.txt_qa_report.insert(tk.END, f"Cases: {report.get('cases')}\n")
            self.txt_qa_report.insert(tk.END, f"Passed: {report.get('passed')}\n")
            self.txt_qa_report.insert(tk.END, f"Failed: {report.get('failed')}\n\n")
            for r in report.get("results") or []:
                flag = "OK" if r.get("pass_all") else "FAIL"
                self.txt_qa_report.insert(tk.END, f"[{flag}] {r.get('case_id')}: {r.get('question')}\n")
            self.status.set(f"Golden eval ferdig: {report.get('passed')}/{report.get('cases')} bestått")

        def _err(e: Exception) -> None:
            messagebox.showerror("Feil", f"Golden eval feilet: {e}")

        if hasattr(self, "run_task"):
            self.run_task(
                "qa_golden",
                _work,
                on_success=_ok,
                on_error=_err,
                start_message="Kjører golden eval…",
                done_message="Golden eval ferdig",
            )
        else:
            try:
                _ok(_work())
            except Exception as e:
                _err(e)
