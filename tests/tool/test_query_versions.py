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


def test_data_hides_internal_columns(ppa_loaded_state):
    """`data` must not surface PDK_ID, CREATED_AT, CREATED_BY (display-safe)."""
    result = query_versions(ppa_loaded_state, project_name="Vanguard")
    for row in result["data"]:
        assert "PDK_ID" not in row, row
        assert "CREATED_AT" not in row, row
        assert "CREATED_BY" not in row, row


def test_pdk_id_by_idx_mapping_present(ppa_loaded_state):
    """pdk_id_by_idx maps IDX (1-based) to actual pdk_id for orchestrator's internal lookup."""
    result = query_versions(ppa_loaded_state, project_name="Vanguard")
    mapping = result.get("pdk_id_by_idx")
    assert isinstance(mapping, dict)
    assert set(mapping.keys()) == {r["IDX"] for r in result["data"]}
    assert all(isinstance(v, int) for v in mapping.values())


def test_auto_selected_when_single_result(ppa_loaded_state):
    """node='3nm' currently maps to a single PDK (Solomon EVT1, pdk_id=881)."""
    result = query_versions(ppa_loaded_state, node="3nm")
    assert result["count"] == 1
    assert result["auto_selected_pdk_id"] == result["pdk_id_by_idx"][1]


def test_no_auto_selected_when_multiple_results(ppa_loaded_state):
    """Multi-row case must NOT include auto_selected_pdk_id."""
    result = query_versions(ppa_loaded_state, project_name="Vanguard")
    assert result["count"] >= 2
    assert "auto_selected_pdk_id" not in result
