"""Tests for query_data tool."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from common.engines import query_data as qd_engine
from common.engines.query_data import query_data

# Init skill from PAVE skill directory
_SKILL_DIR = Path(__file__).resolve().parent.parent / "agents" / "pave" / "skills" / "pave-dk-skill"
qd_engine.init_skill(_SKILL_DIR)


def _make_ctx():
    """Create a mock ADK context with dict-like state."""
    ctx = MagicMock()
    ctx.state = {}
    return ctx


class TestQueryData:
    def test_single_cell_query(self):
        ctx = _make_ctx()
        result = query_data(ctx, "single_cell", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["query_type"] == "single_cell"
        assert result["count"] > 0
        assert all(r["CELL"] == "INV" for r in result["data"])

    def test_single_cell_with_pdk_id(self):
        ctx = _make_ctx()
        result = query_data(ctx, "single_cell", {"project": "S5E9945", "cell": "INV", "pdk_id": 882})
        assert "error" not in result
        assert result["count"] > 0

    def test_compare_cells(self):
        ctx = _make_ctx()
        result = query_data(ctx, "compare_cells", {"project": "S5E9945", "cells": ["INV", "ND2"]})
        assert "error" not in result
        assert result["count"] > 0
        cells_in_result = {r["CELL"] for r in result["data"]}
        assert cells_in_result == {"INV", "ND2"}

    def test_trend_query(self):
        ctx = _make_ctx()
        result = query_data(ctx, "trend", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["count"] > 0

    def test_versions_query(self):
        ctx = _make_ctx()
        result = query_data(ctx, "versions", {"project": "S5E9945"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT"] == "S5E9945" for r in result["data"])

    def test_versions_by_project_name(self):
        ctx = _make_ctx()
        result = query_data(ctx, "versions", {"project": "Solomon"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT_NAME"] == "Solomon" for r in result["data"])

    def test_versions_cached_in_session(self):
        ctx = _make_ctx()
        query_data(ctx, "versions", {"project": "S5E9945"})
        assert "_cache_ANTSDB.PAVE_PDK_VERSION_VIEW" in ctx.state
        query_data(ctx, "versions", {"project": "S5E9955"})

    def test_unknown_query_type(self):
        ctx = _make_ctx()
        result = query_data(ctx, "invalid", {"project": "S5E9945"})
        assert "error" in result

    def test_no_matching_data(self):
        ctx = _make_ctx()
        result = query_data(ctx, "single_cell", {"project": "NONEXIST", "cell": "FAKE"})
        assert "error" not in result
        assert result["count"] == 0

    def test_no_filters(self):
        ctx = _make_ctx()
        result = query_data(ctx, "versions")
        assert "error" not in result
