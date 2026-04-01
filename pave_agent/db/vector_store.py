"""ChromaDB vector store wrapper for RAG retrieval."""

from __future__ import annotations

import logging
from typing import Any

from pave_agent import settings

logger = logging.getLogger(__name__)

_client = None
_collection = None

COLLECTION_NAME = "pave_domain_docs"


def _get_collection():
    """Lazy-initialize ChromaDB client and collection."""
    global _client, _collection
    if _collection is None:
        import chromadb

        _client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB collection '%s' loaded (%d documents)",
            COLLECTION_NAME,
            _collection.count(),
        )
    return _collection


def add_documents(
    documents: list[str],
    metadatas: list[dict[str, Any]] | None = None,
    ids: list[str] | None = None,
) -> None:
    """Add documents to the vector store."""
    collection = _get_collection()
    if ids is None:
        ids = [f"doc_{i}" for i in range(collection.count(), collection.count() + len(documents))]
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    logger.info("Added %d documents to vector store", len(documents))


def search(query: str, n_results: int = 5) -> list[dict[str, Any]]:
    """Search for similar documents.

    Returns list of dicts with 'document', 'metadata', 'distance' keys.
    """
    collection = _get_collection()
    if collection.count() == 0:
        logger.warning("Vector store is empty, returning no results")
        return []

    results = collection.query(query_texts=[query], n_results=n_results)

    docs = []
    for i in range(len(results["documents"][0])):
        docs.append({
            "document": results["documents"][0][i],
            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
            "distance": results["distances"][0][i] if results["distances"] else None,
        })
    return docs
