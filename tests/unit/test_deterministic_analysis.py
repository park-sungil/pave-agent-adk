"""Unit tests for deterministic_analysis fast-path functions."""

import pytest

from pave_agent.tools.deterministic_analysis import (
    benchmark_delta,
    groupby_agg,
    simple_stats,
)


def _row(pdk_id: int, cell: str = "INV", ds: str = "D1", freq: float = 4.0,
         d_power: float = 0.03) -> dict:
    return {
        "PDK_ID": pdk_id,
        "CELL": cell,
        "DS": ds,
        "CORNER": "TT",
        "TEMP": "25",
        "VDD": "0.72",
        "VTH": "SLVT",
        "WNS": "N3",
        "CH": "CH168",
        "FREQ_GHZ": freq,
        "D_POWER": d_power,
    }


class TestBenchmarkDelta:
    def test_two_pdks_compute_delta(self):
        data = [
            _row(881, freq=4.0, d_power=0.030),
            _row(901, freq=4.4, d_power=0.033),
        ]
        result = benchmark_delta(data, [881, 901])
        assert "error" not in result
        assert result["matched_count"] == 1
        assert result["pdk_a"] == 881
        assert result["pdk_b"] == 901
        comp = result["comparison"][0]
        assert comp["FREQ_GHZ_A"] == 4.0
        assert comp["FREQ_GHZ_B"] == 4.4
        assert comp["FREQ_GHZ_delta"] == pytest.approx(0.4, abs=1e-6)
        assert comp["FREQ_GHZ_pct"] == pytest.approx(10.0, abs=1e-3)

    def test_requires_two_pdk_ids(self):
        result = benchmark_delta([_row(881)], [881])
        assert "error" in result

    def test_no_matching_keys_returns_error(self):
        data = [
            _row(881, cell="INV"),
            _row(901, cell="ND2"),  # no overlap with INV
        ]
        result = benchmark_delta(data, [881, 901])
        assert "error" in result


class TestSimpleStats:
    def test_mean_std_min_max_count(self):
        data = [_row(881, freq=4.0), _row(881, freq=4.5), _row(881, freq=5.0)]
        result = simple_stats(data, ["FREQ_GHZ"])
        assert "FREQ_GHZ" in result
        s = result["FREQ_GHZ"]
        assert s["count"] == 3
        assert s["mean"] == pytest.approx(4.5, abs=1e-6)
        assert s["min"] == 4.0
        assert s["max"] == 5.0

    def test_default_metric_columns(self):
        """When columns=None, computes stats for all known metric columns present."""
        data = [_row(881, freq=4.0, d_power=0.03)]
        result = simple_stats(data, None)
        assert "FREQ_GHZ" in result
        assert "D_POWER" in result


class TestGroupbyAgg:
    def test_group_by_cell(self):
        data = [
            _row(881, cell="INV", freq=4.0),
            _row(881, cell="INV", freq=4.4),
            _row(881, cell="ND2", freq=3.0),
        ]
        result = groupby_agg(data, ["CELL"], ["FREQ_GHZ"], agg_func="mean")
        assert "error" not in result
        assert result["count"] == 2
        rows_by_cell = {r["CELL"]: r["FREQ_GHZ"] for r in result["rows"]}
        assert rows_by_cell["INV"] == pytest.approx(4.2, abs=1e-6)
        assert rows_by_cell["ND2"] == 3.0

    def test_invalid_group_col_returns_error(self):
        data = [_row(881)]
        result = groupby_agg(data, ["NONEXISTENT"], ["FREQ_GHZ"])
        assert "error" in result
