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

# Defaults
_DEFAULT_CELL_GROUP = ("INV", "ND2", "NR2")
_DEFAULT_DS_GROUP = ("D1", "D4")
_CELL_AVG_LABEL = "AVG(INV,ND2,NR2)"
_DS_AVG_LABEL = "AVG(D1,D4)"

_METRIC_COLUMNS = [
    "FREQ_GHZ", "D_POWER", "D_ENERGY", "ACCEFF_FF", "ACREFF_KOHM",
    "S_POWER", "IDDQ_NA",
]

_RESULT_ROW_LIMIT = 50

# Precision for markdown table formatting
_METRIC_PRECISION = {
    "FREQ_GHZ": 4,
    "D_POWER": 6,
    "D_ENERGY": 4,
    "ACCEFF_FF": 2,
    "ACREFF_KOHM": 4,
    "S_POWER": 8,
    "IDDQ_NA": 4,
}


def _format_table(
    rows: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> str:
    """Format filtered rows as a markdown table for orchestrator to relay.

    - Skips columns where all rows have the same value (constant columns)
    - Rounds numeric metrics to sensible precision
    - When `metrics` is given, only those metric columns appear (focus
      principle — user requested specific metric(s), code filters columns)
    - Returns ready-to-display markdown string
    """
    if not rows:
        return "(데이터 없음)"

    all_cols = list(rows[0].keys())

    # Determine which columns vary across rows
    varying_cols = []
    for col in all_cols:
        vals = {str(r.get(col)) for r in rows}
        if len(vals) > 1:
            varying_cols.append(col)

    # Determine which metric columns to include
    if metrics is not None:
        # User specified metrics → only include those (and only if present in data)
        metric_cols_to_include = [m for m in metrics if m in all_cols]
    else:
        metric_cols_to_include = [m for m in _METRIC_COLUMNS if m in all_cols]

    # Drop any varying columns that are NOT-requested metric columns
    if metrics is not None:
        unwanted_metrics = set(_METRIC_COLUMNS) - set(metric_cols_to_include)
        varying_cols = [c for c in varying_cols if c not in unwanted_metrics]

    # Always include the chosen metric columns even if constant
    for col in metric_cols_to_include:
        if col not in varying_cols:
            varying_cols.append(col)

    if not varying_cols:
        varying_cols = all_cols

    # Build header
    header = "| " + " | ".join(varying_cols) + " |"
    separator = "| " + " | ".join("---" for _ in varying_cols) + " |"

    # Build rows
    lines = [header, separator]
    for row in rows:
        cells = []
        for col in varying_cols:
            val = row.get(col)
            if val is None:
                cells.append("-")
            elif col in _METRIC_PRECISION and isinstance(val, (int, float)):
                cells.append(f"{val:.{_METRIC_PRECISION[col]}f}")
            else:
                cells.append(str(val))
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)

def _format_search_conditions(conditions: dict[str, Any]) -> str:
    """Compact single-row markdown table summarising the search conditions.

    `conditions` is an ordered dict — keys appear as columns in the order given.
    Used to make the actually-applied filter (after defaults) visible to the
    user without LLM re-formatting.
    """
    cols = list(conditions.keys())
    header = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    row = "| " + " | ".join(str(conditions[c]) for c in cols) + " |"
    return "\n".join([header, sep, row])


# Node → list of processes (hardcoded; not in DB)
_NODE_PROCESSES = {
    "2nm": ["SF2", "SF2P", "SF2PP"],
    "3nm": ["SF3"],
}


def load_versions(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Load all PDK versions into session state (called once at session start)."""
    if _VERSION_CACHE_KEY not in state:
        logger.info("[init] Loading PDK versions from DB")
        state[_VERSION_CACHE_KEY] = oracle_client.execute_query(_VERSION_SQL)
        logger.info("[init] Loaded %d PDK versions", len(state[_VERSION_CACHE_KEY]))
    return state[_VERSION_CACHE_KEY]


def load_default_wns_config(state: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Load default WNS config from DB into session state.

    Returns lookup map keyed by "{project_name} {mask}" string.
    e.g., {"Solomon EVT1": {"HP": "N4", "HD": "N3"}}

    String keys (not tuple) so the dict is JSON-serializable for ADK session storage.
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
    # Oracle CLOB returns a LOB object — read() to get the string content
    if hasattr(config_data, "read"):
        config_data = config_data.read()
    if isinstance(config_data, bytes):
        config_data = config_data.decode("utf-8")
    if isinstance(config_data, str):
        config = json.loads(config_data)
    else:
        config = config_data or {}

    result: dict[str, dict[str, str]] = {}
    for entry in config.get("ppa_summary_default_wns", []):
        project = entry.get("project", "").strip()
        if project:
            result[project] = {
                k: v for k, v in entry.items() if k != "project"
            }

    state[_CONFIG_CACHE_KEY] = result
    logger.info("[init] Loaded %d default WNS entries", len(result))
    return result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

# Columns excluded from `data` (internal-only — orchestrator should never
# show these to the user). pdk_id is still surfaced via pdk_id_by_idx /
# auto_selected_pdk_id so the orchestrator can call query_ppa.
_HIDDEN_VERSION_COLUMNS = {"PDK_ID", "CREATED_AT", "CREATED_BY"}


def query_versions(
    tool_context: ToolContext,
    project: str | None = None,
    project_name: str | None = None,
    process: str | None = None,
    mask: str | None = None,
    node: str | None = None,
    hspice: str | None = None,
    lvs: str | None = None,
    pex: str | None = None,
) -> dict[str, Any]:
    """PDK 버전 목록을 조회한다.

    Args:
        tool_context: ADK tool context (session state).
        project: 프로젝트 코드 (예: S5E9985).
        project_name: 프로젝트명 (예: Vanguard).
        process: 공정명 (예: SF2PP).
        mask: 마스크 버전 (예: EVT0).
        node: 공정 노드. "2nm" → SF2/SF2P/SF2PP, "3nm" → SF3.
            process와 동시 사용 불필요.
        hspice / lvs / pex: 도구 버전. 사용자가 "v1.0" 같이 짧게 줘도
            "V1.0.0.0" 같은 저장값과 prefix-match 됨 (대소문자 무시,
            앞 'v' 제거). 정확한 버전 명시 시 정확 매칭.

    Returns:
        {
            "data": [...],              # 사용자 표시용 (PDK_ID/CREATED_AT/CREATED_BY 제외)
            "count": int,
            "pdk_id_by_idx": {idx: pdk_id},   # IDX → pdk_id 매핑 (orchestrator 가 query_ppa 호출 시 사용)
            "auto_selected_pdk_id": int,       # 결과 1개일 때만 — orchestrator 가 별도 확인 없이 사용
        }
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

    logger.info("[query_versions] filters=%s, node=%s, hspice=%s, lvs=%s, pex=%s",
                filters, node, hspice, lvs, pex)

    try:
        all_rows = load_versions(tool_context.state)
        filtered = _filter_rows(all_rows, filters)

        # Tool-version filters (HSPICE/LVS/PEX) — prefix match (case-insensitive,
        # strip leading 'v'). Allows "v1.0" to match "V1.0.0.0".
        for col, user_val in (("HSPICE", hspice), ("LVS", lvs), ("PEX", pex)):
            if user_val is None:
                continue
            user_norm = str(user_val).lower().lstrip("v")
            filtered = [
                r for r in filtered
                if str(r.get(col, "")).lower().lstrip("v").startswith(user_norm)
            ]

        # Node filter: restrict to processes belonging to the node
        if node is not None:
            node_key = node.lower()
            processes = _NODE_PROCESSES.get(node_key)
            if processes is None:
                return {
                    "error": f"알 수 없는 node: {node}. 사용 가능한 옵션: {', '.join(_NODE_PROCESSES.keys())}",
                }
            filtered = [r for r in filtered if r.get("PROCESS") in processes]

        # Build user-safe display rows + IDX→pdk_id mapping
        display: list[dict[str, Any]] = []
        pdk_id_by_idx: dict[int, int] = {}
        for i, row in enumerate(filtered, 1):
            display.append({
                "IDX": i,
                **{k: v for k, v in row.items() if k not in _HIDDEN_VERSION_COLUMNS},
            })
            pdk_id_by_idx[i] = row.get("PDK_ID")

        result: dict[str, Any] = {
            "data": display,
            "count": len(display),
            "pdk_id_by_idx": pdk_id_by_idx,
        }
        if len(display) == 1:
            result["auto_selected_pdk_id"] = pdk_id_by_idx[1]

        logger.info("[query_versions] returned %d rows (auto_selected=%s)",
                    len(display), result.get("auto_selected_pdk_id"))
        return result
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
    metrics: list[str] | None = None,
) -> dict[str, Any]:
    """PPA 측정 데이터를 조회한다. pdk_id 필수, ch 또는 ch_type 필수.

    빠진 파라미터에 대해 자동으로 default를 적용:
    - PVT (corner/temp/vdd_type): TT/25/NM per-axis default.
    - cell: AVG(INV, ND2, NR2) 평균 집계
    - ds: AVG(D1, D4) 평균 집계
    - wns: dependencies의 default_wns (ch_type 기준)
    - vth: 미적용 (모든 vth 반환)

    Args:
        tool_context: ADK tool context (session state).
        pdk_id: 조회할 PDK ID (필수).
        cell: 셀 타입 (예: INV, ND2). 미명시 시 평균.
        corner: 공정 코너 (예: TT, SSPG).
        temp: 온도 (예: -25, 25, 125).
        vdd: 전압 (예: 0.54, 0.72). 별도 필터로만 사용.
        vdd_type: 전압 타입 (예: UUD, NM, SOD).
        vth: Vth flavor (예: LVT, HVT). 미명시 시 모든 vth.
        ds: 드라이브 스트렝스 (예: D1, D2, D4). 미명시 시 평균.
        wns: nanosheet width. 미명시 시 default_wns.
        ch: cell height (예: CH138). ch 또는 ch_type 중 하나 필수.
        ch_type: cell height 타입 (예: HP, HD, uHD). ch 또는 ch_type 중 하나 필수.
        metrics: 응답 `table` 에 표시할 metric 컬럼 목록 (예: ["FREQ_GHZ"]).
            None 이면 모든 metric 컬럼 포함. 사용자가 특정 metric 만 요청하면
            orchestrator 가 이 인자로 컬럼 필터링. raw 계산 데이터는 그대로
            (세션 캐시에는 모든 컬럼 보존 — analyze/interpret 가 사용).

    Returns:
        {
            "count": int,                          # 결과 행 수
            "pdk_ids": [int],
            "pdk_info": {...},                     # PDK 메타
            "dependencies": {...},                 # PDK 옵션 정보
            "applied_defaults": {...},             # 적용된 default
            "search_conditions_table": str,        # compact key-value markdown 표
            "table": str,                          # 데이터 markdown 표 (≤50행)
            "message": str
        }
        오류 시: {"error": str, "dependencies": {...}}
    """
    logger.info("[query_ppa] pdk_id=%s, cell=%s, corner=%s, temp=%s, vdd=%s, vdd_type=%s, vth=%s, ds=%s, wns=%s, ch=%s, ch_type=%s, metrics=%s",
                pdk_id, cell, corner, temp, vdd, vdd_type, vth, ds, wns, ch, ch_type, metrics)

    try:
        # Load full PPA data + version info + dependencies (all cached)
        cache_key = f"_ppa_data_{pdk_id}"
        if cache_key not in tool_context.state:
            logger.info("[SQL] loading full PPA for pdk_id=%s", pdk_id)
            tool_context.state[cache_key] = oracle_client.execute_query(
                _PPA_SQL,
                {"pdk_id": pdk_id},
            )
            logger.info("[SQL] loaded %d rows for pdk_id=%s", len(tool_context.state[cache_key]), pdk_id)
        rows = tool_context.state[cache_key]

        cached_versions = load_versions(tool_context.state)
        pdk_info = next((r for r in cached_versions if r.get("PDK_ID") == pdk_id), None)

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

        # ch_type is required (or ch which uniquely determines ch_type)
        if ch is None and ch_type is None:
            return {
                "needs_input": "ch_type이 필요합니다. HD, HP, uHD 중 하나를 선택해주세요. (기본값 없음)",
                "options": ["HD", "HP", "uHD"],
                "dependencies": dependencies,
            }

        # Resolve PVT — per-axis defaults (T1: TT/25/NM). User-specified
        # values are kept verbatim; missing axes filled from T1.
        # If user provided raw vdd, don't default vdd_type (vdd pins voltage,
        # vdd_type filter would over-constrain).
        user_specified_vdd = vdd is not None
        applied_defaults: dict[str, str] = {}
        if corner is None:
            corner = "TT"
            applied_defaults["corner"] = corner
        if temp is None:
            temp = "25"
            applied_defaults["temp"] = str(temp)
        if vdd_type is None and not user_specified_vdd:
            vdd_type = "NM"
            applied_defaults["vdd_type"] = vdd_type

        # Build filter dict
        ppa_filters: dict[str, Any] = {
            "CORNER": corner,
            "TEMP": str(temp),
        }
        if user_specified_vdd:
            ppa_filters["VDD"] = vdd
        elif vdd_type is not None:
            ppa_filters["VDD_TYPE"] = vdd_type
        if vth is not None:
            ppa_filters["VTH"] = vth
        if ch is not None:
            ppa_filters["CH"] = ch
        if ch_type is not None:
            ppa_filters["CH_TYPE"] = ch_type

        # Cell default: AVG(INV,ND2,NR2)
        if cell is None:
            ppa_filters["CELL"] = list(_DEFAULT_CELL_GROUP)
            applied_defaults["cell"] = _CELL_AVG_LABEL
        else:
            ppa_filters["CELL"] = cell

        # DS default: AVG(D1,D4)
        if ds is None:
            ppa_filters["DS"] = list(_DEFAULT_DS_GROUP)
            applied_defaults["ds"] = _DS_AVG_LABEL
        else:
            ppa_filters["DS"] = ds

        # WNS default: from dependencies (per ch_type)
        if wns is None:
            # Find chosen ch_type's default_wns
            target_ch_type = ch_type
            if target_ch_type is None and ch is not None:
                # Look up ch_type from ch
                ch_entry = dependencies.get("ch", {}).get(ch)
                if ch_entry:
                    target_ch_type = ch_entry.get("ch_type")
            default_wns: str | None = None
            if target_ch_type:
                for ch_name, ch_entry in dependencies.get("ch", {}).items():
                    if ch_entry.get("ch_type") == target_ch_type:
                        default_wns = ch_entry.get("default_wns")
                        if default_wns:
                            break
            if default_wns:
                ppa_filters["WNS"] = default_wns
                applied_defaults["wns"] = default_wns

        # Filter
        filtered = _filter_rows(rows, ppa_filters)
        logger.info("[query_ppa] filtered %d/%d rows for pdk_id=%s", len(filtered), len(rows), pdk_id)

        # Aggregate: average over CELL and/or DS if defaulted
        aggregate_cols: list[str] = []
        labels: dict[str, str] = {}
        if cell is None:
            aggregate_cols.append("CELL")
            labels["CELL"] = _CELL_AVG_LABEL
        if ds is None:
            aggregate_cols.append("DS")
            labels["DS"] = _DS_AVG_LABEL
        if aggregate_cols:
            filtered = _aggregate_avg(filtered, aggregate_cols, _METRIC_COLUMNS, labels)
            logger.info("[query_ppa] aggregated to %d rows (collapsed: %s)", len(filtered), aggregate_cols)

        # Cache filtered result for analyze
        tool_context.state[f"_ppa_filtered_{pdk_id}"] = filtered

        # Build search conditions table (compact key-value, single row)
        cell_label = cell if cell is not None else _CELL_AVG_LABEL
        ds_label = ds if ds is not None else _DS_AVG_LABEL
        wns_label = wns if wns is not None else applied_defaults.get("wns", "auto")
        search_conditions = {
            "corner": corner,
            "temp": str(temp),
            "vdd": str(vdd) if user_specified_vdd else f"vdd_type={vdd_type}",
            "vth": vth or "all",
            "cell": cell_label,
            "ds": ds_label,
            "wns": wns_label,
            "ch_type": ch_type or (ch or "-"),
        }
        search_conditions_table = _format_search_conditions(search_conditions)

        # Build response
        result: dict[str, Any] = {
            "count": len(filtered),
            "pdk_ids": [pdk_id],
            "dependencies": dependencies,
            "applied_defaults": applied_defaults,
            "search_conditions_table": search_conditions_table,
        }
        if pdk_info:
            result["pdk_info"] = {k: pdk_info[k] for k in _CANDIDATE_COLUMNS if k in pdk_info}

        # Return pre-formatted markdown table (not raw data) so the
        # orchestrator LLM can relay it without touching numbers.
        # If `metrics` is given, code filters columns to only those metrics
        # (focus principle, deterministic — LLM never picks columns).
        if len(filtered) == 0:
            result["table"] = "(조회 결과 없음)"
            result["message"] = "조회 결과 없음."
        elif len(filtered) <= _RESULT_ROW_LIMIT:
            result["table"] = _format_table(filtered, metrics=metrics)
            result["message"] = f"{len(filtered)}건 조회됨."
        else:
            result["message"] = (
                f"{len(filtered)}건 조회됨 (>{_RESULT_ROW_LIMIT}행). "
                f"분석이 필요하면 analyze를 호출하세요."
            )

        return result
    except Exception as e:
        logger.error("query_ppa failed: %s", e, exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _aggregate_avg(
    rows: list[dict[str, Any]],
    aggregate_cols: list[str],
    metric_cols: list[str],
    labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Average metric_cols across rows, grouping by all columns except aggregate_cols.

    aggregate_cols: columns to collapse (e.g., ['CELL'])
    metric_cols: numeric columns to average
    labels: replacement values for collapsed columns (e.g., {'CELL': 'AVG(INV,ND2,NR2)'})
    """
    if not rows:
        return []

    all_cols = list(rows[0].keys())
    group_cols = [c for c in all_cols if c not in aggregate_cols and c not in metric_cols]

    groups: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        key = tuple(r.get(c) for c in group_cols)
        if key not in groups:
            entry: dict[str, Any] = {c: r.get(c) for c in group_cols}
            entry.update(labels)
            entry.update({c: [] for c in metric_cols})
            groups[key] = entry
        for c in metric_cols:
            v = r.get(c)
            if v is not None:
                groups[key][c].append(v)

    result = []
    for entry in groups.values():
        for c in metric_cols:
            vals = entry[c]
            entry[c] = sum(vals) / len(vals) if vals else None
        result.append(entry)
    return result


def _extract_dependencies(
    rows: list[dict[str, Any]],
    default_wns_map: dict[str, dict[str, str]],
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
    config_key = f"{project_name} {mask}" if project_name and mask else ""
    config_entry = default_wns_map.get(config_key)
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
