"""Tool tests for analyze fast-path routing.

The deterministic fast paths (benchmark for 2 PDKs, stats for keyword match)
must NOT call the LLM. We monkeypatch pave_agent.llm.call_llm to fail loudly
if invoked, and assert successful results.
"""

import time

import pytest

from pave_agent.tools.analyze import analyze
from pave_agent.tools.query_data import query_ppa


def _populate(ctx, pdk_id: int) -> None:
    """Run query_ppa to populate _ppa_filtered_{pdk_id} for analyze to consume."""
    result = query_ppa(ctx, pdk_id=pdk_id, ch_type="HP")
    assert "error" not in result, result


def _llm_must_not_be_called(*args, **kwargs):
    pytest.fail("LLM was called — fast path should be deterministic")


def test_benchmark_two_pdks_no_llm_call(ppa_loaded_state, monkeypatch):
    monkeypatch.setattr("pave_agent.llm.call_llm", _llm_must_not_be_called)

    _populate(ppa_loaded_state, 913)
    _populate(ppa_loaded_state, 914)

    t0 = time.time()
    result = analyze(ppa_loaded_state, pdk_ids=[913, 914], analysis_request="FREQ 비교")
    elapsed = time.time() - t0

    assert "error" not in result, result
    assert "deterministic" in result.get("message", "")
    assert "### PDK" in result["formatted_result"]
    # New format: ratio-only, transposed (PDK A / PDK B / Ratio rows)
    assert "PDK A" in result["formatted_result"]
    assert "Ratio" in result["formatted_result"]
    assert "Delta" not in result["formatted_result"]
    # 100ms is generous — typical run is <20ms
    assert elapsed < 0.5, f"deterministic fast path took {elapsed:.3f}s"


def test_stats_keyword_no_llm_call(ppa_loaded_state, monkeypatch):
    monkeypatch.setattr("pave_agent.llm.call_llm", _llm_must_not_be_called)
    _populate(ppa_loaded_state, 914)
    result = analyze(
        ppa_loaded_state,
        pdk_ids=[914],
        analysis_request="FREQ_GHZ 평균을 알려줘",
    )
    assert "error" not in result, result
    assert "deterministic" in result.get("message", "")
