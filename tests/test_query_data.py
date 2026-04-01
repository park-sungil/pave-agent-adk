"""Tests for query_data tool."""

from pave_lib.tools.query_data import query_data, _normalize_param


class TestNormalizeParam:
    def test_english_lowercase(self):
        assert _normalize_param("vth") == "VTH"

    def test_english_mixed_case(self):
        assert _normalize_param("Ion") == "ION"

    def test_korean(self):
        assert _normalize_param("문턱전압") == "VTH"
        assert _normalize_param("누설전류") == "IOFF"

    def test_unknown_param_uppercased(self):
        assert _normalize_param("custom_param") == "CUSTOM_PARAM"


class TestQueryData:
    def test_single_cell_query(self):
        result = query_data(process_node="N5", cell_name="INVD1", query_type="single_cell")
        assert "error" not in result
        assert result["query_type"] == "single_cell"
        assert result["count"] > 0
        assert all(r["CELL_NAME"] == "INVD1" for r in result["data"])

    def test_single_cell_with_version(self):
        result = query_data(process_node="N5", cell_name="INVD1", version="v1.0", query_type="single_cell")
        assert "error" not in result
        assert all(r["VERSION"] == "v1.0" for r in result["data"])

    def test_single_cell_missing_cell_name(self):
        result = query_data(process_node="N5", query_type="single_cell")
        assert "error" in result

    def test_trend_query(self):
        result = query_data(process_node="N5", cell_name="INVD1", parameters=["VTH"], query_type="trend")
        assert "error" not in result
        assert result["count"] > 0

    def test_versions_query(self):
        result = query_data(process_node="N5", query_type="versions")
        assert "error" not in result
        assert result["count"] > 0

    def test_unknown_query_type(self):
        result = query_data(process_node="N5", query_type="invalid")
        assert "error" in result

    def test_no_matching_data(self):
        result = query_data(process_node="N99", cell_name="FAKE", query_type="single_cell")
        assert "error" not in result
        assert result["count"] == 0
