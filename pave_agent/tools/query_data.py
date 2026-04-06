"""query_data tool: DB query executor with PDK resolution and session caching.

No LLM calls. Resolves PDK versions from cached data, loads PPA data once
per PDK into session state, and filters in Python.
"""

from __future__ import annotations

import logging
from typing import Any

from google.adk.tools import ToolContext

from pave_agent.db import oracle_client

logger = logging.getLogger(__name__)

_VERSION_TABLE = "ANTSDB.PAVE_PDK_VERSION_VIEW"
_PPA_TABLE = "ANTSDB.PAVE_PPA_DATA_VIEW"
_VERSION_CACHE_KEY = f"_cache_{_VERSION_TABLE}"

_VERSION_SQL = f"""\
SELECT PDK_ID, PROCESS, PROJECT, PROJECT_NAME, MASK, DK_GDS,
       VDD_NOMINAL, HSPICE, LVS, PEX, CREATED_AT, CREATED_BY
FROM {_VERSION_TABLE}
WHERE (PROJECT, MASK, DK_GDS, HSPICE, LVS, PEX, CREATED_AT) IN (
    SELECT PROJECT, MASK, DK_GDS, HSPICE, LVS, PEX, MAX(CREATED_AT)
    FROM {_VERSION_TABLE}
    GROUP BY PROJECT, MASK, DK_GDS, HSPICE, LVS, PEX
)"""

_PPA_SQL = f"""\
SELECT PDK_ID, CELL, DS, CORNER, TEMP, VDD, VTH,
       FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, ACREFF_KOHM,
       S_POWER, IDDQ_NA, WNS, WNS_VAL, CH, CH_TYPE
FROM {_PPA_TABLE}
WHERE PDK_ID = :pdk_id"""

_PDK_FILTER_KEYS = {"process", "project", "project_name", "mask", "dk_gds"}
_TOOL_VERSION_KEYS = {"hspice", "lvs", "pex"}
_PPA_FILTER_KEYS = {"cell", "corner", "temp", "vdd", "vth", "ds", "wns", "ch"}
_CANDIDATE_COLUMNS = [
    "PDK_ID", "PROCESS", "PROJECT_NAME", "MASK", "DK_GDS",
    "VDD_NOMINAL", "HSPICE", "LVS", "PEX",
    "CREATED_AT", "CREATED_BY",
]


def load_versions(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Load all PDK versions into session state (called once at session start)."""
    if _VERSION_CACHE_KEY not in state:
        logger.info("[init] Loading PDK versions from DB")
        state[_VERSION_CACHE_KEY] = oracle_client.execute_query(_VERSION_SQL)
        logger.info("[init] Loaded %d PDK versions", len(state[_VERSION_CACHE_KEY]))
    return state[_VERSION_CACHE_KEY]


def query_data(
    tool_context: ToolContext,
    query_type: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """DB 데이터를 조회한다.

    Args:
        tool_context: ADK tool context (session state).
        query_type: "versions" (PDK 목록) 또는 "ppa_data" (PPA 측정 데이터).
        filters: 쿼리 필터 조건.

    Returns:
        versions: {"data": [...], "count": int}
        ppa_data: {"count": int, "pdk_ids": [...], "unique_values": {...}}
        candidates: {"candidates": [...], "message": str}
        error: {"error": str}
    """
    filters = filters if isinstance(filters, dict) else {}

    try:
        if query_type == "versions":
            return _query_versions(tool_context, filters)
        elif query_type == "ppa_data":
            return _query_ppa_data(tool_context, filters)
        else:
            return {"error": f"Unknown query_type: {query_type}"}
    except Exception as e:
        logger.error("query_data failed: %s", e, exc_info=True)
        return {"error": str(e)}


def _query_versions(
    tool_context: ToolContext,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """PDK 버전 목록 조회 (캐시에서 Python 필터링)."""
    all_rows = load_versions(tool_context.state)
    filtered = _filter_rows(all_rows, filters)
    results = [{"IDX": i, **row} for i, row in enumerate(filtered, 1)]
    return {"data": results, "count": len(results)}


def _query_ppa_data(
    tool_context: ToolContext,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """PPA 측정 데이터 조회 (PDK resolve → 전체 로드 → Python 필터링)."""
    # Resolve PDK IDs
    cached_versions = load_versions(tool_context.state)
    resolve_result = _resolve_pdks(cached_versions, filters)

    if resolve_result["status"] == "candidates":
        return {
            "candidates": resolve_result["candidates"],
            "message": "PDK 버전이 여러 개입니다. 아래 목록을 사용자에게 테이블로 보여주고 번호로 선택을 요청하세요. 사용자가 선택하면 해당 PDK_ID로 query_data('ppa_data', {'pdk_id': 선택된_ID})를 다시 호출하세요.",
        }
    elif resolve_result["status"] == "no_match":
        return {
            "error": "조건에 맞는 PDK가 없습니다.",
            "available": resolve_result.get("available", {}),
        }

    pdk_ids = resolve_result["pdk_ids"]

    # Load full PPA data per PDK (once), cache in session, filter in Python
    ppa_filters = {k: v for k, v in filters.items() if k in _PPA_FILTER_KEYS}
    all_results: list[dict[str, Any]] = []

    for pdk_id in pdk_ids:
        cache_key = f"_ppa_data_{pdk_id}"
        if cache_key not in tool_context.state:
            logger.info("[SQL] loading full PPA for pdk_id=%s", pdk_id)
            tool_context.state[cache_key] = oracle_client.execute_query(
                _PPA_SQL,
                {"pdk_id": pdk_id},
            )
        rows = tool_context.state[cache_key]
        filtered = _filter_rows(rows, ppa_filters)
        all_results.extend(filtered)

    return _summarize(all_results, pdk_ids)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _summarize(
    rows: list[dict[str, Any]],
    pdk_ids: list[int],
) -> dict[str, Any]:
    """Return a summary instead of raw data to keep LLM context small."""
    if not rows:
        return {"count": 0, "pdk_ids": pdk_ids, "message": "조회 결과 없음."}

    unique = {}
    for col in ("CELL", "CORNER", "TEMP", "VDD", "VTH", "DS", "CH"):
        vals = sorted({str(r[col]) for r in rows if col in r})
        if vals:
            unique[col] = vals

    return {
        "count": len(rows),
        "pdk_ids": pdk_ids,
        "unique_values": unique,
        "message": f"{len(rows)}건 조회됨. analyze에 pdk_ids를 전달하세요.",
    }


def _filter_rows(
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
) -> list[dict[str, Any]]:
    """Filter rows by matching filter keys to column names (case-insensitive, AND logic)."""
    if not filters:
        return rows
    conditions = {k.upper(): v for k, v in filters.items()}
    if not rows:
        return rows
    all_cols = list(rows[0].keys())

    def _matches(row: dict, key: str, val: Any) -> bool:
        cols = [c for c in all_cols if c.startswith(key)]
        if not cols:
            return True
        return any(
            row.get(c) == val or (isinstance(val, list) and row.get(c) in val)
            for c in cols
        )

    return [
        r for r in rows
        if all(_matches(r, key, val) for key, val in conditions.items())
    ]


def _resolve_pdks(
    cached_versions: list[dict[str, Any]],
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Resolve PDK versions from cached data.

    Returns:
        {"status": "resolved", "pdk_ids": [int, ...]}
        {"status": "candidates", "candidates": [dict, ...]}
        {"status": "no_match", "available": {...}}
    """
    if "pdk_id" in filters:
        return {"status": "resolved", "pdk_ids": [filters["pdk_id"]]}

    # Step 1: Narrow by PROCESS / PROJECT / PROJECT_NAME / MASK / DK_GDS
    rows = cached_versions
    for key in _PDK_FILTER_KEYS:
        val = filters.get(key)
        if val is None:
            continue
        upper_key = key.upper()
        if upper_key in ("PROJECT", "PROJECT_NAME"):
            rows = [r for r in rows if r.get("PROJECT") == val or r.get("PROJECT_NAME") == val]
        else:
            rows = [r for r in rows if r.get(upper_key) == val]

    if not rows:
        available_projects = sorted({r.get("PROJECT_NAME", "") for r in cached_versions})
        return {"status": "no_match", "available": {"projects": available_projects}}

    # Step 2: HSPICE/LVS/PEX explicitly specified
    tool_filters = {k: filters[k] for k in _TOOL_VERSION_KEYS if k in filters}
    if tool_filters:
        for key, val in tool_filters.items():
            rows = [r for r in rows if r.get(key.upper()) == val]
        if not rows:
            return {"status": "no_match", "available": {}}

    if not rows:
        return {"status": "no_match", "available": {}}

    if len(rows) == 1:
        return {"status": "resolved", "pdk_ids": [rows[0]["PDK_ID"]]}

    # Multiple rows: different MASKs = all resolved, same MASK different DK_GDS = ambiguous
    project_mask_groups: dict[tuple, list] = {}
    for r in rows:
        key = (r.get("PROJECT"), r.get("MASK"))
        project_mask_groups.setdefault(key, []).append(r)

    has_ambiguity = any(len(group) > 1 for group in project_mask_groups.values())
    if has_ambiguity:
        candidates = [{col: r.get(col) for col in _CANDIDATE_COLUMNS} for r in rows]
        return {"status": "candidates", "candidates": candidates}

    return {"status": "resolved", "pdk_ids": [r["PDK_ID"] for r in rows]}
