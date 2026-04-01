"""RAG retriever: searches vector store and formats results for LLM context."""

from __future__ import annotations

from pave_lib.db import vector_store


def retrieve(query: str, top_k: int = 5) -> str:
    """Retrieve relevant document chunks and format as context string.

    Args:
        query: Search query (question or analysis result summary).
        top_k: Number of chunks to retrieve.

    Returns:
        Formatted string of retrieved document chunks for LLM context.
    """
    results = vector_store.search(query, n_results=top_k)

    if not results:
        return "(관련 참조 문서가 없습니다.)"

    chunks = []
    for i, doc in enumerate(results, 1):
        source = doc["metadata"].get("source", "unknown")
        chunks.append(f"[참조 {i}] (출처: {source})\n{doc['document']}")

    return "\n\n---\n\n".join(chunks)
