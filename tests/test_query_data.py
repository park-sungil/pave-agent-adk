"""Tests for query_data tool."""

import pytest

from pave_agent.cache import data_cache
from pave_agent.tools.query_data import query_data


class TestQueryData:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        data_cache.clear()
        yield
        data_cache.clear()

    def test_single_cell_query(self):
        result = query_data("single_cell", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["query_type"] == "single_cell"
        assert result["count"] > 0
        assert all(r["CELL"] == "INV" for r in result["data"])

    def test_single_cell_with_pdk_id(self):
        result = query_data("single_cell", {"project": "S5E9945", "cell": "INV", "pdk_id": 882})
        assert "error" not in result
        assert result["count"] > 0

    def test_compare_cells(self):
        result = query_data("compare_cells", {"project": "S5E9945", "cells": ["INV", "ND2"]})
        assert "error" not in result
        assert result["count"] > 0
        cells_in_result = {r["CELL"] for r in result["data"]}
        assert cells_in_result == {"INV", "ND2"}

    def test_trend_query(self):
        result = query_data("trend", {"project": "S5E9945", "cell": "INV"})
        assert "error" not in result
        assert result["count"] > 0

    def test_versions_query(self):
        result = query_data("versions", {"project": "S5E9945"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT"] == "S5E9945" for r in result["data"])

    def test_versions_by_project_name(self):
        result = query_data("versions", {"project": "Solomon"})
        assert "error" not in result
        assert result["count"] > 0
        assert all(r["PROJECT_NAME"] == "Solomon" for r in result["data"])

    def test_versions_cached(self):
        r1 = query_data("versions", {"project": "S5E9945"})
        assert data_cache.has("PAVE_PDK_VERSION_VIEW")
        r2 = query_data("versions", {"project": "S5E9955"})
        assert r1["count"] > 0
        assert r2["count"] > 0

    def test_unknown_query_type(self):
        result = query_data("invalid", {"project": "S5E9945"})
        assert "error" in result

    def test_no_matching_data(self):
        result = query_data("single_cell", {"project": "NONEXIST", "cell": "FAKE"})
        assert "error" not in result
        assert result["count"] == 0

    def test_no_filters(self):
        result = query_data("versions")
        assert "error" not in result
