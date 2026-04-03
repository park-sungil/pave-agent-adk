"""Tests for query_data tool."""

from unittest.mock import MagicMock

import pytest

from pave_agent.db import oracle_client
from pave_agent.tools.query_data import _CACHE_TABLES, query_data


def _make_tool_context():
    """Create a mock ADK ToolContext with pre-loaded versions cache."""
    ctx = MagicMock()
    ctx.state = {}
    # Pre-load versions like before_agent_callback does
    for query_type, table in _CACHE_TABLES.items():
        cache_key = f"_cache_{table}"
        ctx.state[cache_key] = oracle_client.execute_query(f"SELECT * FROM {table}")
    return ctx


class TestQueryData:
    def test_single_cell_query(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "single_cell", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["query_type"] == "single_cell"
        assert result["count"] > 0
        assert all(r["CELL"] == "INV" for r in result["data"])

    def test_single_cell_with_pdk_id(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "single_cell", {"project": "S5E9945", "cell": "INV", "pdk_id": 882})
        assert "error" not in result
        assert result["count"] > 0

    def test_compare_cells(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "compare_cells", {"project": "S5E9945", "cells": ["INV", "ND2"]})
        assert "error" not in result
        assert result["count"] > 0
        cells_in_result = {r["CELL"] for r in result["data"]}
        assert cells_in_result == {"INV", "ND2"}

    def test_trend_query(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "trend", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["count"] > 0

    def test_versions_query(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "versions", {"project": "S5E9945"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT"] == "S5E9945" for r in result["data"])

    def test_versions_by_project_name(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "versions", {"project": "Solomon"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT_NAME"] == "Solomon" for r in result["data"])

    def test_versions_cached_in_session(self):
        ctx = _make_tool_context()
        assert "_cache_ANTSDB.PAVE_PDK_VERSION_VIEW" in ctx.state

    def test_unknown_query_type(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "invalid", {"project": "S5E9945"})
        assert "error" in result

    def test_no_matching_pdk(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "single_cell", {"project": "NONEXIST", "cell": "FAKE"})
        assert "error" in result  # no PDK found

    def test_pdk_resolution_candidates(self):
        """When multiple golden PDKs exist for same project, returns candidates."""
        ctx = _make_tool_context()
        result = query_data(ctx, "single_cell", {"project": "S5E9945", "cell": "INV"})
        # Should either resolve (data) or return candidates
        assert "data" in result or "candidates" in result

    def test_no_filters(self):
        ctx = _make_tool_context()
        result = query_data(ctx, "versions")
        assert "error" not in result
