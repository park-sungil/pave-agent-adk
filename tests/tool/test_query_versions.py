"""Tool tests for query_versions."""

from pave_agent.tools.query_data import query_versions


def test_filter_by_project_name(ppa_loaded_state):
    """All returned rows must have PROJECT_NAME matching the filter."""
    result = query_versions(ppa_loaded_state, project_name="Vanguard")
    assert "error" not in result
    assert result["count"] > 0
    assert all(r["PROJECT_NAME"] == "Vanguard" for r in result["data"])


def test_node_filter_2nm(ppa_loaded_state):
    """node='2nm' must restrict to SF2 / SF2P / SF2PP processes."""
    result = query_versions(ppa_loaded_state, node="2nm")
    assert "error" not in result
    assert result["count"] > 0
    assert all(r["PROCESS"] in ("SF2", "SF2P", "SF2PP") for r in result["data"])


def test_unknown_node_returns_error(ppa_loaded_state):
    result = query_versions(ppa_loaded_state, node="99nm")
    assert "error" in result
