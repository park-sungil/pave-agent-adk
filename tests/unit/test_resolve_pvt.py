"""Unit tests for query_data._resolve_pvt PVT-triple resolution."""

from pave_agent.tools.query_data import _resolve_pvt


def test_no_input_returns_t1_default():
    """Nothing specified → default T1 triple (TT/25/NM), no error."""
    pvt, error = _resolve_pvt(None, None, None)
    assert error is None
    assert pvt == {"corner": "TT", "temp": "25", "vdd_type": "NM"}


def test_ambiguous_sspg_returns_error():
    """SSPG alone matches T2 (125/SOD) and T3 (-25/SUD) → ambiguous error."""
    pvt, error = _resolve_pvt("SSPG", None, None)
    assert pvt is None
    assert error is not None
    assert "모호" in error
