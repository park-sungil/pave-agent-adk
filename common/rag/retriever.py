"""RAG retriever: fetches relevant documents from external RAG API."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# TODO: Replace with actual internal RAG API endpoint
_RAG_API_URL: str = ""


def retrieve(query: str, top_k: int = 5) -> str:
    """Retrieve relevant document chunks and format as context string.

    Args:
        query: Search query (question or analysis result summary).
        top_k: Number of chunks to retrieve.

    Returns:
        Formatted string of retrieved document chunks for LLM context.
    """
    if not _RAG_API_URL:
        return "(관련 참조 문서가 없습니다.)"

    # TODO: Call internal RAG API
    # response = requests.post(_RAG_API_URL, json={"query": query, "top_k": top_k})
    # results = response.json()

    return "(관련 참조 문서가 없습니다.)"
