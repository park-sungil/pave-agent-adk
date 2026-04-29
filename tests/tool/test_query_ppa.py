"""Tool tests for query_ppa.

Asserts default-resolution behavior and session-state population:
- ch_type missing → needs_input
- ch_type provided → table (markdown), no `data` field, _ppa_filtered_{pdk_id} populated
- user-specified vdd → applied_defaults excludes vdd_type
- minimal call → all major defaults applied
"""

from pave_agent.tools.query_data import query_ppa

# Vanguard EVT0 PDK ID — exists in mock seed with WNS config (HP→N4).
_PDK_ID = 914


def test_missing_ch_type_returns_needs_input(ppa_loaded_state):
    """Without ch or ch_type, query_ppa must return needs_input + options list."""
    result = query_ppa(ppa_loaded_state, pdk_id=_PDK_ID)
    assert "needs_input" in result
    assert result["options"] == ["HD", "HP", "uHD"]


def test_with_ch_type_populates_state(ppa_loaded_state):
    """Providing ch_type yields a markdown table (no raw `data`) and caches filtered rows."""
    result = query_ppa(ppa_loaded_state, pdk_id=_PDK_ID, ch_type="HP")
    assert "error" not in result
    assert "needs_input" not in result
    assert "table" in result, f"missing table; keys={list(result.keys())}"
    assert isinstance(result["table"], str)
    assert "|" in result["table"], "table should be markdown with pipe separators"
    # Numbers stay in session, not in the LLM-bound response
    assert "data" not in result
    assert ppa_loaded_state.state.get(f"_ppa_filtered_{_PDK_ID}"), "filtered cache not populated"


def test_user_vdd_skips_vdd_type_default(ppa_loaded_state):
    """When the user pins vdd, vdd_type default must not be applied (would over-constrain)."""
    result = query_ppa(ppa_loaded_state, pdk_id=_PDK_ID, ch_type="HP", vdd=0.72)
    assert "applied_defaults" in result
    applied = result["applied_defaults"]
    assert "vdd_type" not in applied, applied
    # corner/temp still defaulted (user didn't specify them)
    assert applied.get("corner") == "TT"
    assert applied.get("temp") == "25"


def test_applied_defaults_present_when_omitted(ppa_loaded_state):
    """Minimal call (only pdk_id + ch_type) → corner/temp/vdd_type/cell/ds/wns all defaulted."""
    result = query_ppa(ppa_loaded_state, pdk_id=_PDK_ID, ch_type="HP")
    applied = result.get("applied_defaults", {})
    expected = {"corner", "temp", "vdd_type", "cell", "ds", "wns"}
    assert expected <= set(applied.keys()), f"missing keys: {expected - set(applied.keys())}"
