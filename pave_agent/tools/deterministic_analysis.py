"""Deterministic analysis functions — no LLM, no sandbox.

These cover the most common analysis patterns (80%+) and execute in <100ms.
analyze.py routes to these when a known pattern is detected, falling back
to LLM code generation only for ad-hoc requests.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

_METRIC_COLUMNS = [
    "FREQ_GHZ", "D_POWER", "D_ENERGY", "ACCEFF_FF", "ACREFF_KOHM",
    "S_POWER", "IDDQ_NA",
]

_MERGE_KEYS = ["CELL", "DS", "CORNER", "TEMP", "VDD", "VTH", "WNS", "CH"]


def _to_native(obj: Any) -> Any:
    """Convert numpy/pandas types to JSON-serializable Python native types."""
    import numpy as np

    if isinstance(obj, dict):
        return {str(k) if not isinstance(k, (str, int, float, bool)) else k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (pd.DataFrame, pd.Series)):
        return _to_native(obj.to_dict())
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, np.bool_):
        return bool(obj)
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def benchmark_delta(
    data: list[dict[str, Any]],
    pdk_ids: list[int],
    metrics: list[str] | None = None,
    baseline_pdk_id: int | None = None,
) -> dict[str, Any]:
    """Compare two PDKs: merge by same conditions, compute delta and % change.

    `baseline_pdk_id` (optional): if given and present in `pdk_ids`, that
    PDK is treated as `pdk_a` (baseline). Delta and pct are then expressed
    as `(target - baseline) / baseline`. If omitted, the first id in
    `pdk_ids` is the baseline (back-compat).

    Returns:
        {"comparison": [per-row dicts], "summary": {metric: {avg_delta, avg_pct}}, "pdk_a": baseline, "pdk_b": target, ...}
    """
    if len(pdk_ids) != 2:
        return {"error": "benchmark_delta requires exactly 2 pdk_ids."}

    metrics = metrics or _METRIC_COLUMNS
    if baseline_pdk_id is not None and baseline_pdk_id in pdk_ids:
        pdk_a = baseline_pdk_id
        pdk_b = next(p for p in pdk_ids if p != baseline_pdk_id)
    else:
        pdk_a, pdk_b = pdk_ids

    df = pd.DataFrame(data)
    df_a = df[df["PDK_ID"] == pdk_a].copy()
    df_b = df[df["PDK_ID"] == pdk_b].copy()

    # Find merge keys that actually exist in the data
    available_keys = [k for k in _MERGE_KEYS if k in df.columns]
    available_metrics = [m for m in metrics if m in df.columns]

    if not available_keys or not available_metrics:
        return {"error": "데이터에 매칭 가능한 키 또는 메트릭이 없습니다."}

    merged = df_a.merge(df_b, on=available_keys, suffixes=("_A", "_B"))

    if merged.empty:
        return {"error": "동일 조건으로 매칭되는 데이터가 없습니다."}

    # Compute delta and pct for each metric
    comparison = []
    for _, row in merged.iterrows():
        entry = {k: row[k] for k in available_keys}
        for m in available_metrics:
            a_val = row.get(f"{m}_A")
            b_val = row.get(f"{m}_B")
            if a_val is not None and b_val is not None:
                delta = b_val - a_val
                pct = (delta / a_val * 100) if a_val != 0 else None
                entry[f"{m}_A"] = round(a_val, 6)
                entry[f"{m}_B"] = round(b_val, 6)
                entry[f"{m}_delta"] = round(delta, 6)
                entry[f"{m}_pct"] = round(pct, 4) if pct is not None else None
        comparison.append(entry)

    # Summary: mean delta/pct per metric
    summary = {}
    for m in available_metrics:
        deltas = [r[f"{m}_delta"] for r in comparison if r.get(f"{m}_delta") is not None]
        pcts = [r[f"{m}_pct"] for r in comparison if r.get(f"{m}_pct") is not None]
        summary[m] = {
            "avg_delta": round(sum(deltas) / len(deltas), 6) if deltas else None,
            "avg_pct": round(sum(pcts) / len(pcts), 4) if pcts else None,
        }

    return _to_native({
        "comparison": comparison,
        "summary": summary,
        "matched_count": len(comparison),
        "pdk_a": pdk_a,
        "pdk_b": pdk_b,
    })


def simple_stats(
    data: list[dict[str, Any]],
    columns: list[str] | None = None,
) -> dict[str, Any]:
    """Compute mean, std, min, max for requested columns."""
    df = pd.DataFrame(data)
    columns = columns or [c for c in _METRIC_COLUMNS if c in df.columns]

    result = {}
    for col in columns:
        if col not in df.columns:
            continue
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        result[col] = {
            "mean": round(float(series.mean()), 6),
            "std": round(float(series.std()), 6),
            "min": round(float(series.min()), 6),
            "max": round(float(series.max()), 6),
            "count": int(len(series)),
        }

    return _to_native(result)


def groupby_agg(
    data: list[dict[str, Any]],
    group_cols: list[str],
    agg_cols: list[str] | None = None,
    agg_func: str = "mean",
) -> dict[str, Any]:
    """Group by specified columns and aggregate metrics."""
    df = pd.DataFrame(data)
    agg_cols = agg_cols or [c for c in _METRIC_COLUMNS if c in df.columns]
    group_cols = [c for c in group_cols if c in df.columns]

    if not group_cols or not agg_cols:
        return {"error": "유효한 그룹 컬럼 또는 집계 컬럼이 없습니다."}

    grouped = df.groupby(group_cols)[agg_cols].agg(agg_func)
    rows = grouped.reset_index().to_dict(orient="records")

    return _to_native({
        "grouped_by": group_cols,
        "agg_func": agg_func,
        "rows": rows,
        "count": len(rows),
    })
