from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .env_loader import load_env
from .rag_bridge import make_context
from .rag_index import get_or_create_collection
from .settings_profiles import load_settings


SYSTEM_PROMPT = """Du er en hjelpsom fagassistent for norske revisorer.

Regler:
- Bruk kun informasjon fra konteksten når du svarer.
- Hvis konteksten ikke inneholder svaret: si tydelig at du ikke kan finne det i kildene.
- Når du refererer til en kilde: nevn kilde-id og gjerne anker (f.eks. "Revisorloven §1-1").
- Svar på norsk, kort og presist, men med nok detaljer til at det kan brukes i praksis.
"""


def _format_sources(chunks: List[Dict[str, Any]]) -> str:
    seen: set[str] = set()
    lines: List[str] = []
    for c in chunks:
        meta = c.get("metadata") or {}
        sid = meta.get("source_id") or meta.get("source_title") or meta.get("file_name") or "KILDE"
        anchor = meta.get("anchor")
        key = f"{sid}|{anchor or ''}"
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"- {sid}{(' ' + anchor) if anchor else ''}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Spørsmål mot RAG-indeks (CLI)")
    parser.add_argument("question", nargs="?", help="Spørsmål (i anførselstegn)")
    parser.add_argument("--db", default=None, help="Chroma db-path (default fra settings/env)")
    parser.add_argument("--collection", default=None, help="Collection-navn (default fra settings/env)")
    parser.add_argument("--library", default=None, help="Path til kildebibliotek.json (valgfri)")
    parser.add_argument("--k", type=int, default=5, help="Antall treff i retrieval")
    parser.add_argument("--show-context", action="store_true", help="Skriv ut kontekst som brukes")
    parser.add_argument("--no-llm", action="store_true", help="Ikke kall LLM (kun retrieval)")

    args = parser.parse_args(argv)

    if not args.question:
        print(
            "Du må gi et spørsmål. Eksempel: python run_qa_cli.py --show-context \"Hva sier ISA 230 om dokumentasjon?\""
        )
        return 2

    # 1) last .env (API key osv.)
    load_env()

    # 2) settings
    cfg = load_settings()
    db_path = args.db or cfg.db_path
    collection_name = args.collection or cfg.collection
    library_path = args.library

    # 3) collection
    try:
        col = get_or_create_collection(
            db_path=db_path,
            collection_name=collection_name,
            embedding_model=cfg.embedding_model,
        )
    except Exception as e:
        print(f"Kunne ikke åpne collection: {e}")
        return 1

    # 4) context
    context, used_chunks = make_context(
        args.question,
        col,
        n_results=max(1, args.k),
        library_path=library_path,
        expand_relations=True,
    )

    if args.show_context:
        print("\n[Kontekst brukt i prompt]\n")
        print(context)
        print("\n[Kilder]\n")
        print(_format_sources([{"metadata": c.metadata} for c in used_chunks]))

    if args.no_llm:
        return 0

    # 5) LLM
    try:
        from openai import OpenAI  # lokal import

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=os.getenv("OPENAI_BASE_URL") or None)
        model = os.getenv("OPENAI_CHAT_MODEL") or cfg.chat_model

        user_prompt = f"Spørsmål: {args.question}\n\nKontekst:\n{context}\n\nSvar:"
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        answer = resp.choices[0].message.content or ""
        print("\n[Svar]\n")
        print(answer.strip())

        print("\n[Kilder]\n")
        print(_format_sources([{"metadata": c.metadata} for c in used_chunks]))

        return 0
    except Exception as e:
        print(f"LLM-kall feilet: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
