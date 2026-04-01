"""Tests for interpret tool components."""

from pave_agent.rag.retriever import retrieve
from pave_agent.rag.indexer import chunk_text


class TestChunkText:
    def test_small_text_single_chunk(self):
        text = "Short text."
        chunks = chunk_text(text, chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_large_text_multiple_chunks(self):
        paragraphs = ["Paragraph " + str(i) + ". " + "x" * 100 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1

    def test_empty_text(self):
        chunks = chunk_text("")
        assert len(chunks) == 0 or chunks == [""]


class TestRetriever:
    def test_empty_store_returns_fallback(self):
        # With empty vector store, should return fallback message
        result = retrieve("VTH meaning")
        assert "관련 참조 문서가 없습니다" in result
