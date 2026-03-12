from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from chromadb.api.models.Collection import Collection
else:
    Collection = Any  # pragma: no cover


@dataclass
class OpenAIEmbeddingFunction:
    """Chroma embedding function using OpenAI.

    Merk: Enkel wrapper for OpenAI embeddings.
    Vi definerer `.name` for kompatibilitet med enkelte Chroma-versjoner.
    """

    api_key: str
    model_name: str = "text-embedding-3-small"
    base_url: Optional[str] = None

    def __post_init__(self) -> None:
        self.name = "openai"  # enkelte Chroma-versjoner forventer dette
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY mangler (sett i .env eller miljøvariabler)")

        try:
            from openai import OpenAI  # lokal import (gjør modulen testbar uten openai installert)
        except Exception as e:  # pragma: no cover
            raise ImportError("openai er ikke installert. Kjør: pip install -r requirements.txt") from e

        self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def __call__(self, texts: List[str]) -> List[List[float]]:
        res = self._client.embeddings.create(model=self.model_name, input=texts)
        return [d.embedding for d in res.data]


def get_or_create_collection(
    *,
    db_path: str = "ragdb",
    collection_name: str = "revisjon",
    embedding_model: Optional[str] = None,
) -> Collection:
    """Oppretter/åpner Chroma-kolleksjon."""
    try:
        import chromadb  # lokal import (gjør modulen testbar uten chromadb installert)
    except Exception as e:  # pragma: no cover
        raise ImportError("chromadb er ikke installert. Kjør: pip install -r requirements.txt") from e

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model_name = (embedding_model or os.getenv("OPENAI_EMBED_MODEL") or "text-embedding-3-small").strip()
    base_url = os.getenv("OPENAI_BASE_URL") or None

    emb_fn = OpenAIEmbeddingFunction(api_key=api_key, model_name=model_name, base_url=base_url)
    client = chromadb.PersistentClient(path=db_path)

    col = client.get_or_create_collection(
        name=collection_name,
        embedding_function=emb_fn,
        metadata={"hnsw:space": "cosine"},
    )
    return col


def add_documents(collection: Collection, docs: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
    if not docs:
        return
    collection.add(documents=docs, metadatas=metadatas, ids=ids)


def upsert_documents(collection: Collection, docs: List[str], metadatas: List[Dict[str, Any]], ids: List[str]) -> None:
    if not docs:
        return
    collection.upsert(documents=docs, metadatas=metadatas, ids=ids)


def _flatten_ids(ids: Any) -> List[str]:
    """Normaliserer 'ids' fra Chroma get() til en flat liste."""
    if ids is None:
        return []
    if isinstance(ids, list):
        # Noen kan returnere nested lister, selv om get() vanligvis er flat.
        if ids and isinstance(ids[0], list):
            out: List[str] = []
            for sub in ids:
                out.extend([str(x) for x in (sub or [])])
            return out
        return [str(x) for x in ids]
    return [str(ids)]


def _get_ids_best_effort(collection: Collection, *, where: Optional[Dict[str, Any]] = None) -> List[str]:
    """Henter alle ids (ev. filtrert av where) best-effort.

    Bruker paginering hvis tilgjengelig i collection.get(limit, offset).
    """
    page_size = 500
    offset = 0
    all_ids: List[str] = []

    # Forsøk med paginering
    while True:
        try:
            res = collection.get(where=where, include=[], limit=page_size, offset=offset)
        except TypeError:
            # Eldre API: ingen limit/offset
            res = collection.get(where=where, include=[])
            all_ids = _flatten_ids(res.get("ids"))
            return all_ids
        except Exception:
            # get() finnes ikke eller feiler: gi opp
            return []

        ids = _flatten_ids(res.get("ids"))
        if not ids:
            break
        all_ids.extend(ids)
        if len(ids) < page_size:
            break
        offset += page_size

    return all_ids


def delete_where(collection: Collection, where: Dict[str, Any]) -> int:
    """Sletter dokumenter som matcher where.

    Returnerer antall ids vi forsøkte å slette (kan avvike fra faktisk slettet i Chroma).
    """
    if not where:
        return 0

    # Foretrukket: direkte where-delete
    try:
        collection.delete(where=where)
        return 0
    except TypeError:
        # gammel/annen signatur -> fallback
        pass
    except Exception:
        # fallback under
        pass

    # Fallback: hent ids og slett i batch
    ids = _get_ids_best_effort(collection, where=where)
    if not ids:
        return 0

    batch = 2000
    for i in range(0, len(ids), batch):
        collection.delete(ids=ids[i : i + batch])
    return len(ids)


def delete_all_documents(collection: Collection) -> int:
    """Sletter ALT i collection.

    Returnerer antall ids vi forsøkte å slette (best effort).
    """
    # Foretrukket: where={}
    try:
        collection.delete(where={})
        return 0
    except TypeError:
        pass
    except Exception:
        pass

    ids = _get_ids_best_effort(collection)
    if not ids:
        return 0
    batch = 2000
    for i in range(0, len(ids), batch):
        collection.delete(ids=ids[i : i + batch])
    return len(ids)


def query_collection(
    collection: Collection,
    query_text: str,
    *,
    n_results: int = 5,
    where: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"query_texts": [query_text], "n_results": n_results}
    if where:
        kwargs["where"] = where
    return collection.query(**kwargs)
