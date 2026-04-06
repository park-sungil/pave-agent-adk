"""DB query tools: query_versions and query_ppa.

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
SELECT PDK_ID, CELL, DS, CORNER, TEMP, VDD, VDD_TYPE, VTH,
       FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, ACREFF_KOHM,
       S_POWER, IDDQ_NA, WNS, WNS_VAL, CH, CH_TYPE
FROM {_PPA_TABLE}
WHERE PDK_ID = :pdk_id"""

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


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

def query_versions(
    tool_context: ToolContext,
    project: str | None = None,
    project_name: str | None = None,
    process: str | None = None,
    mask: str | None = None,
) -> dict[str, Any]:
    """PDK 버전 목록을 조회한다.

    Args:
        tool_context: ADK tool context (session state).
        project: 프로젝트 코드 (예: S5E9985).
        project_name: 프로젝트명 (예: Vanguard).
        process: 공정명 (예: SF2PP).
        mask: 마스크 버전 (예: EVT0).

    Returns:
        {"data": [...], "count": int}
    """
    filters = {}
    if project is not None:
        filters["PROJECT"] = project
    if project_name is not None:
        filters["PROJECT_NAME"] = project_name
    if process is not None:
        filters["PROCESS"] = process
    if mask is not None:
        filters["MASK"] = mask

    logger.info("[query_versions] filters=%s", filters)

    try:
        all_rows = load_versions(tool_context.state)
        filtered = _filter_rows(all_rows, filters)
        results = [{"IDX": i, **row} for i, row in enumerate(filtered, 1)]
        return {"data": results, "count": len(results)}
    except Exception as e:
        logger.error("query_versions failed: %s", e, exc_info=True)
        return {"error": str(e)}


def query_ppa(
    tool_context: ToolContext,
    pdk_id: int,
    cell: str | None = None,
    corner: str | None = None,
    temp: float | None = None,
    vdd: float | None = None,
    vdd_type: str | None = None,
    vth: str | None = None,
    ds: str | None = None,
    wns: str | None = None,
    ch: str | None = None,
    ch_type: str | None = None,
) -> dict[str, Any]:
    """PPA 측정 데이터를 조회한다. pdk_id 필수.

    pdk_id를 모르면 먼저 query_versions로 PDK ID를 확인하세요.

    Args:
        tool_context: ADK tool context (session state).
        pdk_id: 조회할 PDK ID (필수). query_versions 결과에서 확인.
        cell: 셀 타입 (예: INV, ND2).
        corner: 공정 코너 (예: TT, SSPG).
        temp: 온도 (예: -25, 25, 125).
        vdd: 전압 (예: 0.54, 0.72).
        vdd_type: 전압 타입 (예: UUD, SUD, UD, NM, OD, SOD).
        vth: Vth flavor (예: LVT, HVT).
        ds: 드라이브 스트렝스 (예: D1, D2).
        wns: nanosheet width (예: N1, N2).
        ch: cell height (예: CH138, CH148).
        ch_type: cell height 타입 (예: HP, HD, uHD).

    Returns:
        {"count": int, "pdk_ids": [...], "unique_values": {...}}
        세션에 _ppa_data_{pdk_id}로 저장됨.
    """
    logger.info("[query_ppa] pdk_id=%s, cell=%s, corner=%s, temp=%s, vdd=%s, vdd_type=%s, vth=%s, ds=%s, wns=%s, ch=%s, ch_type=%s",
                pdk_id, cell, corner, temp, vdd, vdd_type, vth, ds, wns, ch, ch_type)

    try:
        ppa_filters: dict[str, Any] = {}
        if cell is not None:
            ppa_filters["CELL"] = cell
        if corner is not None:
            ppa_filters["CORNER"] = corner
        if temp is not None:
            ppa_filters["TEMP"] = temp
        if vdd is not None:
            ppa_filters["VDD"] = vdd
        if vdd_type is not None:
            ppa_filters["VDD_TYPE"] = vdd_type
        if vth is not None:
            ppa_filters["VTH"] = vth
        if ds is not None:
            ppa_filters["DS"] = ds
        if wns is not None:
            ppa_filters["WNS"] = wns
        if ch is not None:
            ppa_filters["CH"] = ch
        if ch_type is not None:
            ppa_filters["CH_TYPE"] = ch_type

        cache_key = f"_ppa_data_{pdk_id}"
        if cache_key not in tool_context.state:
            logger.info("[SQL] loading full PPA for pdk_id=%s", pdk_id)
            tool_context.state[cache_key] = oracle_client.execute_query(
                _PPA_SQL,
                {"pdk_id": pdk_id},
            )
        rows = tool_context.state[cache_key]
        filtered = _filter_rows(rows, ppa_filters)

        return _summarize(filtered, [pdk_id])
    except Exception as e:
        logger.error("query_ppa failed: %s", e, exc_info=True)
        return {"error": str(e)}


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
    for col in ("CELL", "CORNER", "TEMP", "VDD", "VDD_TYPE", "VTH", "DS", "WNS", "CH", "CH_TYPE"):
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

    def _eq(a: Any, b: Any) -> bool:
        """Compare values, falling back to float comparison for numeric strings."""
        if a == b:
            return True
        try:
            return float(a) == float(b)
        except (ValueError, TypeError):
            return False

    def _matches(row: dict, key: str, val: Any) -> bool:
        cols = [c for c in all_cols if c.startswith(key)]
        if not cols:
            return True
        return any(
            _eq(row.get(c), val) or (isinstance(val, list) and any(_eq(row.get(c), v) for v in val))
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
    _pdk_filter_keys = {"process", "project", "project_name", "mask", "dk_gds"}
    for key in _pdk_filter_keys:
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
    _tool_version_keys = {"hspice", "lvs", "pex"}
    tool_filters = {k: filters[k] for k in _tool_version_keys if k in filters}
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
