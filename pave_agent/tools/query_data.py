"""DB query tools: query_versions and query_ppa.

No LLM calls. Resolves PDK versions from cached data, loads PPA data once
per PDK into session state, and filters in Python.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.tools import ToolContext

from pave_agent.db import oracle_client

logger = logging.getLogger(__name__)

_VERSION_TABLE = "ANTSDB.PAVE_PDK_VERSION_VIEW"
_PPA_TABLE = "ANTSDB.PAVE_PPA_DATA_VIEW"
_CONFIG_TABLE = "AT9.PDKPAS_CONFIG_JSON_FAV"
_VERSION_CACHE_KEY = f"_cache_{_VERSION_TABLE}"
_CONFIG_CACHE_KEY = f"_cache_{_CONFIG_TABLE}"

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

_CONFIG_SQL = f"""\
SELECT CONFIG_DATA FROM {_CONFIG_TABLE}
ORDER BY CREATED_AT DESC FETCH FIRST 1 ROW ONLY"""

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


def load_default_wns_config(state: dict[str, Any]) -> dict[tuple, dict[str, str]]:
    """Load default WNS config from DB into session state.

    Returns lookup map: {(project_name, mask): {ch_type: wns}}
    e.g., {("Solomon", "EVT1"): {"HP": "N4", "HD": "N3"}}
    """
    if _CONFIG_CACHE_KEY in state:
        return state[_CONFIG_CACHE_KEY]

    logger.info("[init] Loading default WNS config from DB")
    rows = oracle_client.execute_query(_CONFIG_SQL)
    if not rows:
        logger.warning("[init] No default WNS config found")
        state[_CONFIG_CACHE_KEY] = {}
        return state[_CONFIG_CACHE_KEY]

    config_data = rows[0].get("CONFIG_DATA")
    if isinstance(config_data, str):
        config = json.loads(config_data)
    else:
        config = config_data or {}

    result: dict[tuple, dict[str, str]] = {}
    for entry in config.get("ppa_summary_default_wns", []):
        project = entry.get("project", "")
        # "Solomon EVT1" → ("Solomon", "EVT1")
        parts = project.rsplit(" ", 1)
        if len(parts) == 2:
            result[(parts[0], parts[1])] = {
                k: v for k, v in entry.items() if k != "project"
            }

    state[_CONFIG_CACHE_KEY] = result
    logger.info("[init] Loaded %d default WNS entries", len(result))
    return result


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
        logger.info("[query_versions] returned %d rows", len(results))
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
            logger.info("[SQL] loaded %d rows for pdk_id=%s", len(tool_context.state[cache_key]), pdk_id)
        rows = tool_context.state[cache_key]

        # Look up PDK version info
        cached_versions = load_versions(tool_context.state)
        pdk_info = next((r for r in cached_versions if r.get("PDK_ID") == pdk_id), None)

        # Derive dependencies (cached per pdk_id)
        deps_key = f"_ppa_deps_{pdk_id}"
        if deps_key not in tool_context.state:
            default_wns_map = load_default_wns_config(tool_context.state)
            project_name = pdk_info.get("PROJECT_NAME") if pdk_info else None
            mask = pdk_info.get("MASK") if pdk_info else None
            tool_context.state[deps_key] = _extract_dependencies(
                rows, default_wns_map, project_name, mask
            )
            logger.info("[query_ppa] extracted dependencies for pdk_id=%s", pdk_id)
        dependencies = tool_context.state[deps_key]

        filtered = _filter_rows(rows, ppa_filters)
        logger.info("[query_ppa] filtered %d/%d rows for pdk_id=%s", len(filtered), len(rows), pdk_id)

        result = _summarize(filtered, [pdk_id], dependencies)
        if pdk_info:
            result["pdk_info"] = {k: pdk_info[k] for k in _CANDIDATE_COLUMNS if k in pdk_info}
        return result
    except Exception as e:
        logger.error("query_ppa failed: %s", e, exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _summarize(
    rows: list[dict[str, Any]],
    pdk_ids: list[int],
    dependencies: dict[str, Any],
) -> dict[str, Any]:
    """Return a summary instead of raw data to keep LLM context small."""
    if not rows:
        return {
            "count": 0,
            "pdk_ids": pdk_ids,
            "dependencies": dependencies,
            "message": "조회 결과 없음.",
        }

    return {
        "count": len(rows),
        "pdk_ids": pdk_ids,
        "dependencies": dependencies,
        "message": f"{len(rows)}건 조회됨.",
    }


def _extract_dependencies(
    rows: list[dict[str, Any]],
    default_wns_map: dict[tuple, dict[str, str]],
    project_name: str | None,
    mask: str | None,
) -> dict[str, Any]:
    """Extract domain-aware dependencies from cached PDK rows.

    Output structure:
        {
            "ch": {ch_name: {ch_type, ds_list, wns_list, default_wns?}},
            "corner": {corner_name: {vdd_list: [{vdd, vdd_type}, ...]}},
            "cell": [list],
            "temp": [list],
            "vth": [list],
        }
    """
    # Group CH data
    ch_data: dict[str, dict[str, Any]] = {}
    for r in rows:
        ch = r.get("CH")
        if not ch:
            continue
        d = ch_data.setdefault(ch, {
            "ch_type": r.get("CH_TYPE"),
            "ds": set(),
            "wns_map": {},
        })
        if r.get("DS"):
            d["ds"].add(r["DS"])
        if r.get("WNS"):
            d["wns_map"][r["WNS"]] = r.get("WNS_VAL")

    # Build CH result with default_wns resolution
    config_entry = default_wns_map.get((project_name, mask))
    ch_result: dict[str, dict[str, Any]] = {}
    for ch_name in sorted(ch_data.keys()):
        d = ch_data[ch_name]
        ch_type = d["ch_type"]
        # Sort WNS by wns_val (lowest first)
        wns_sorted = sorted(d["wns_map"].keys(), key=lambda w: d["wns_map"][w] or 0)

        entry: dict[str, Any] = {
            "ch_type": ch_type,
            "ds_list": sorted(d["ds"]),
            "wns_list": [{"wns": w, "wns_val": d["wns_map"][w]} for w in wns_sorted],
        }

        # Resolve default_wns
        if config_entry is None:
            # Whole project missing in config → fallback to lowest WNS
            if wns_sorted:
                entry["default_wns"] = wns_sorted[0]
        elif ch_type in config_entry:
            entry["default_wns"] = config_entry[ch_type]
        # else: ch_type missing in existing config entry → omit default_wns

        ch_result[ch_name] = entry

    # Group corner → VDD list
    corner_data: dict[str, dict[str, str]] = {}
    for r in rows:
        corner, vdd = r.get("CORNER"), r.get("VDD")
        if not corner or vdd is None:
            continue
        corner_data.setdefault(corner, {})[vdd] = r.get("VDD_TYPE")

    corner_result: dict[str, dict[str, Any]] = {}
    for corner in sorted(corner_data.keys()):
        sorted_vdds = sorted(corner_data[corner].keys(), key=lambda v: float(v))
        corner_result[corner] = {
            "vdd_list": [
                {"vdd": v, "vdd_type": corner_data[corner][v]} for v in sorted_vdds
            ]
        }

    return {
        "ch": ch_result,
        "corner": corner_result,
        "cell": sorted({r["CELL"] for r in rows if "CELL" in r}),
        "temp": sorted({r["TEMP"] for r in rows if "TEMP" in r}, key=float),
        "vth": sorted({r["VTH"] for r in rows if "VTH" in r}),
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
