"""Tests for interpret tool components."""

from pave_agent.rag.retriever import retrieve


class TestRetriever:
    def test_empty_api_returns_fallback(self):
        result = retrieve("VTH meaning")
        assert "관련 참조 문서가 없습니다" in result
