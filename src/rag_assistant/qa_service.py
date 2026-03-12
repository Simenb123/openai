from __future__ import annotations

"""rag_assistant.qa_service

Små, testbare hjelpefunksjoner for spørsmål/svar og pilot-evaluering.

Hvorfor egen modul?
- `qa_cli.py` skal være enkel CLI-entrypoint.
- GUI trenger samme kjernefunksjonalitet uten å duplisere logikk.
- Vi ønsker å teste retrieval/formattering uten Tkinter og uten å måtte kalle OpenAI.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from .env_loader import load_env
from .golden_eval import load_golden_cases, run_golden_eval, save_report
from .rag_bridge import ContextChunk, make_context
from .rag_index import get_or_create_collection
from .settings_profiles import Settings, load_settings


SYSTEM_PROMPT = """Du er en hjelpsom fagassistent for norske revisorer.

Regler:
- Bruk kun informasjon fra konteksten når du svarer.
- Hvis konteksten ikke inneholder svaret: si tydelig at du ikke kan finne det i kildene.
- Når du refererer til en kilde: nevn kilde-id og gjerne anker (f.eks. \"Revisorloven §1-1\").
- Svar på norsk, kort og presist, men med nok detaljer til at det kan brukes i praksis.
"""


@dataclass(frozen=True)
class QueryOutcome:
    question: str
    context: str
    chunks: List[ContextChunk]
    sources_text: str
    answer: Optional[str] = None


@dataclass(frozen=True)
class GoldenOutcome:
    report: Dict
    report_path: Path


def format_sources(chunks: List[ContextChunk]) -> str:
    seen: set[str] = set()
    lines: List[str] = []
    for c in chunks:
        meta = c.metadata or {}
        sid = meta.get("source_id") or meta.get("source_title") or meta.get("file_name") or "KILDE"
        anchor = meta.get("anchor")
        key = f"{sid}|{anchor or ''}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {sid}{(' ' + anchor) if anchor else ''}")
    return "\n".join(lines)


def _call_openai_chat(*, model: str, question: str, context: str, api_key: Optional[str], base_url: Optional[str]) -> str:
    try:
        from openai import OpenAI  # lokal import
    except Exception as e:  # pragma: no cover
        raise RuntimeError("openai-biblioteket er ikke installert") from e

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY mangler. Legg den i .env eller miljøvariabler.")

    client = OpenAI(api_key=api_key, base_url=base_url)
    user_prompt = f"Spørsmål: {question}\n\nKontekst:\n{context}\n\nSvar:"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def retrieve_only(
    question: str,
    *,
    settings: Optional[Settings] = None,
    db_path: Optional[str] = None,
    collection_name: Optional[str] = None,
    library_path: Optional[str | Path] = None,
    n_results: int = 5,
    expand_relations: bool = True,
) -> QueryOutcome:
    """Hent kun retrieval/context, ingen LLM-kall."""
    load_env()
    cfg = settings or load_settings()
    db = db_path or cfg.db_path
    coll = collection_name or cfg.collection

    col = get_or_create_collection(db_path=db, collection_name=coll, embedding_model=cfg.embedding_model)
    context, used_chunks = make_context(
        question,
        col,
        n_results=max(1, int(n_results)),
        library_path=str(library_path) if library_path else None,
        expand_relations=bool(expand_relations),
    )
    return QueryOutcome(
        question=question,
        context=context,
        chunks=used_chunks,
        sources_text=format_sources(used_chunks),
        answer=None,
    )


def run_query(
    question: str,
    *,
    settings: Optional[Settings] = None,
    db_path: Optional[str] = None,
    collection_name: Optional[str] = None,
    library_path: Optional[str | Path] = None,
    n_results: int = 5,
    expand_relations: bool = True,
    use_llm: bool = False,
) -> QueryOutcome:
    """Kjør retrieval, og valgfritt LLM-svar."""
    outcome = retrieve_only(
        question,
        settings=settings,
        db_path=db_path,
        collection_name=collection_name,
        library_path=library_path,
        n_results=n_results,
        expand_relations=expand_relations,
    )
    if not use_llm:
        return outcome

    cfg = settings or load_settings()
    answer = _call_openai_chat(
        model=cfg.chat_model,
        question=question,
        context=outcome.context,
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL") or cfg.base_url,
    )
    return QueryOutcome(
        question=outcome.question,
        context=outcome.context,
        chunks=outcome.chunks,
        sources_text=outcome.sources_text,
        answer=answer,
    )


def run_golden_suite(
    *,
    golden_path: str | Path,
    report_path: str | Path,
    settings: Optional[Settings] = None,
    db_path: Optional[str] = None,
    collection_name: Optional[str] = None,
    library_path: Optional[str | Path] = None,
    n_results: int = 5,
    expand_relations: bool = True,
) -> GoldenOutcome:
    """Kjør golden-eval og lagre rapport."""
    load_env()
    cfg = settings or load_settings()
    db = db_path or cfg.db_path
    coll = collection_name or cfg.collection
    col = get_or_create_collection(db_path=db, collection_name=coll, embedding_model=cfg.embedding_model)

    cases = load_golden_cases(golden_path)
    report = run_golden_eval(
        cases,
        collection=col,
        library_path=str(library_path) if library_path else None,
        n_results=max(1, int(n_results)),
        expand_relations=bool(expand_relations),
    )
    save_report(report, report_path)
    return GoldenOutcome(report=report, report_path=Path(report_path))
