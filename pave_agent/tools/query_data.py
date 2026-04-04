"""query_data tool: Pure code SQL query builder and executor.

No LLM calls. Assembles SQL from templates defined in sql.md,
executes against DB. Uses ADK session state for caching.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from google.adk.tools import ToolContext

from pave_agent import settings
from pave_agent.db import oracle_client

logger = logging.getLogger(__name__)


def _load_skill() -> tuple[dict[str, str], dict[str, str]]:
    """Parse SQL templates and cache config from sql.md."""
    sql_path = settings.SKILL_DIR / "references" / "sql.md"
    if not sql_path.exists():
        logger.warning("sql.md not found at %s", sql_path)
        return {}, {}

    content = sql_path.read_text(encoding="utf-8")

    templates: dict[str, str] = {}
    for match in re.finditer(
        r"###\s+(\w+)\s*\n```sql\s*\n(.*?)```",
        content,
        re.DOTALL,
    ):
        templates[match.group(1)] = match.group(2).strip()

    cache_tables: dict[str, str] = {}
    cache_section = re.search(r"## Cache\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if cache_section:
        for row in re.finditer(
            r"^\|\s*([\w]+)\s*\|\s*([\w.]+)\s*\|$",
            cache_section.group(1),
            re.MULTILINE,
        ):
            qtype = row.group(1)
            table = row.group(2)
            if qtype in ("query_type", "---", ""):
                continue
            cache_tables[qtype] = table

    logger.info("Loaded sql skill: %d templates, %d cache tables", len(templates), len(cache_tables))
    return templates, cache_tables


_TEMPLATES, _CACHE_TABLES = _load_skill()


def query_data(
    tool_context: ToolContext,
    query_type: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """sql.md에 정의된 SQL 템플릿을 기반으로 DB 데이터를 조회한다.

    Args:
        tool_context: ADK tool context (session state for caching).
        query_type: 쿼리 유형. sql.md에 정의된 템플릿명 또는 캐시 테이블명.
        filters: 쿼리 필터 조건.

    Returns:
        {"data": [...], "count": int, "query_type": str}.
        PDK 후보가 여러 개면 {"candidates": [...], "message": str}.
        오류 시 {"error": str}.
    """
    filters = filters or {}

    try:
        # --- cached tables (versions): full scan + Python filter ---
        cache_table = _CACHE_TABLES.get(query_type)
        if cache_table:
            cache_key = f"_cache_{cache_table}"
            if cache_key not in tool_context.state:
                tool_context.state[cache_key] = oracle_client.execute_query(
                    f"SELECT * FROM {cache_table}"
                )
            all_rows = tool_context.state[cache_key]
            filtered = _filter_rows(all_rows, filters)
            results = [{"IDX": i, **row} for i, row in enumerate(filtered, 1)]
            return {"data": results, "count": len(results), "query_type": query_type}

        # --- SQL template queries: resolve PDK first ---
        template = _TEMPLATES.get(query_type)
        if template is None:
            return {"error": f"Unknown query_type: {query_type}"}

        # PDK resolution — only for templates that use :pdk_id
        needs_pdk = ":pdk_id" in template
        versions_table = _CACHE_TABLES.get("versions")
        if needs_pdk and versions_table:
            cache_key = f"_cache_{versions_table}"
            cached_versions = tool_context.state.get(cache_key, [])
            resolve_result = _resolve_pdks(cached_versions, filters)

            if resolve_result["status"] == "resolved":
                # Single or multiple confirmed PDK IDs
                pdk_ids = resolve_result["pdk_ids"]
            elif resolve_result["status"] == "candidates":
                return {
                    "candidates": resolve_result["candidates"],
                    "message": "PDK 버전을 선택해주세요.",
                    "query_type": query_type,
                }
            else:  # no_match
                return {
                    "error": "조건에 맞는 PDK가 없습니다.",
                    "available": resolve_result.get("available", {}),
                    "query_type": query_type,
                }
        elif needs_pdk:
            pdk_ids = [filters["pdk_id"]] if "pdk_id" in filters else []
        else:
            # Template doesn't need pdk_id — execute directly
            params, format_args = _build_params(template, filters)
            sql = template.format(**format_args)
            sql = _strip_optional_clauses(sql, params)
            logger.info("[SQL] query_type=%s\n%s\nparams=%s", query_type, sql, params)
            results = oracle_client.execute_query(sql, params)
            return {"data": results, "count": len(results), "query_type": query_type}

        # Execute SQL for each resolved PDK, store in session state per pdk_id
        all_results: list[dict[str, Any]] = []
        for pdk_id in pdk_ids:
            params, format_args = _build_params(template, {**filters, "pdk_id": pdk_id})
            sql = template.format(**format_args)
            sql = _strip_optional_clauses(sql, params)
            logger.info("[SQL] query_type=%s pdk_id=%s\n%s\nparams=%s", query_type, pdk_id, sql, params)
            rows = oracle_client.execute_query(sql, params)
            tool_context.state[f"_ppa_data_{pdk_id}"] = rows
            all_results.extend(rows)

        return _summarize(all_results, pdk_ids)

    except Exception as e:
        logger.error("query_data failed: %s", e, exc_info=True)
        return {"error": str(e)}


def _summarize(
    rows: list[dict[str, Any]],
    pdk_ids: list[int],
) -> dict[str, Any]:
    """Return a summary instead of raw data to keep LLM context small.

    Full data is stored in session state as _ppa_data_{pdk_id}.
    """
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
    """Filter cached rows by matching filter keys to column names (case-insensitive, AND logic).

    A filter key matches any column whose name starts with the key (e.g., "PROJECT"
    matches both "PROJECT" and "PROJECT_NAME"). A row passes if ANY matching column
    contains the filter value.
    """
    if not filters:
        return rows
    conditions = {k.upper(): v for k, v in filters.items()}
    if not rows:
        return rows
    all_cols = list(rows[0].keys())

    def _matches(row: dict, key: str, val: Any) -> bool:
        cols = [c for c in all_cols if c.startswith(key)]
        if not cols:
            return True  # skip filter keys that don't match any column
        return any(
            row.get(c) == val or (isinstance(val, list) and row.get(c) in val)
            for c in cols
        )

    return [
        r for r in rows
        if all(_matches(r, key, val) for key, val in conditions.items())
    ]


_PDK_FILTER_KEYS = {"process", "project", "project_name", "mask", "dk_gds"}
_TOOL_VERSION_KEYS = {"hspice", "lvs", "pex"}
_CANDIDATE_COLUMNS = [
    "PDK_ID", "PROCESS", "PROJECT_NAME", "MASK", "DK_GDS",
    "IS_GOLDEN", "VDD_NOMINAL", "HSPICE", "LVS", "PEX",
    "CREATED_AT", "CREATED_BY",
]


def _resolve_pdks(
    cached_versions: list[dict[str, Any]],
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Resolve PDK versions from cached data following PDK Selection Rules in sql.md.

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
        # Dedup by 6-tuple, pick latest CREATED_AT
        rows = _dedup_by_created_at(rows)
    else:
        # Step 3: HSPICE/LVS/PEX not specified — use IS_GOLDEN
        golden = [r for r in rows if r.get("IS_GOLDEN") == 1]
        if golden:
            rows = golden

    if not rows:
        return {"status": "no_match", "available": {}}

    if len(rows) == 1:
        return {"status": "resolved", "pdk_ids": [rows[0]["PDK_ID"]]}

    # Multiple rows: check if ambiguous (same PROJECT+MASK, different DK_GDS)
    # Different MASKs = all resolved (return all pdk_ids)
    # Same MASK, different DK_GDS = ambiguous (ask user)
    project_mask_groups: dict[tuple, list] = {}
    for r in rows:
        key = (r.get("PROJECT"), r.get("MASK"))
        project_mask_groups.setdefault(key, []).append(r)

    has_ambiguity = any(len(group) > 1 for group in project_mask_groups.values())
    if has_ambiguity:
        candidates = [{col: r.get(col) for col in _CANDIDATE_COLUMNS} for r in rows]
        return {"status": "candidates", "candidates": candidates}

    # All rows are from different (PROJECT, MASK) — all resolved
    return {"status": "resolved", "pdk_ids": [r["PDK_ID"] for r in rows]}


def _dedup_by_created_at(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """For rows with same 6-tuple, keep the one with latest CREATED_AT."""
    best: dict[tuple, dict[str, Any]] = {}
    for r in rows:
        key = (r.get("PROJECT"), r.get("MASK"), r.get("DK_GDS"),
               r.get("HSPICE"), r.get("LVS"), r.get("PEX"))
        existing = best.get(key)
        if existing is None or str(r.get("CREATED_AT", "")) > str(existing.get("CREATED_AT", "")):
            best[key] = r
    return list(best.values())


def _build_params(
    template: str,
    filters: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Build SQL bind params and format args from filters and template placeholders.

    Returns:
        (params, format_args)
        - params: bind parameters for SQL execution (e.g., {":project": "Solomon"})
        - format_args: Python .format() args for template placeholders (e.g., pdk_clause, cell_placeholders)
    """
    params: dict[str, Any] = {}
    format_args: dict[str, str] = {}

    # Find all :bind_var references in template
    bind_vars = set(re.findall(r":(\w+)", template))

    for key, value in filters.items():
        lower_key = key.lower()

        if isinstance(value, list):
            # IN clause: expand list into numbered params
            placeholders = ", ".join(f":{lower_key}_{i}" for i in range(len(value)))
            for i, v in enumerate(value):
                params[f"{lower_key}_{i}"] = v
            format_args[f"{lower_key}_placeholders"] = placeholders
        else:
            params[lower_key] = value

    return params, format_args


def _strip_optional_clauses(sql: str, params: dict[str, Any]) -> str:
    """Remove AND clauses whose bind variables are not in params.

    For the ppa_data template, only :pdk_id is required. All other AND lines
    (e.g., AND CELL = :cell) are stripped if the corresponding filter wasn't provided.
    This lets one template handle any combination of filters.
    """
    lines = sql.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith("AND"):
            bind_vars = re.findall(r":(\w+)", stripped)
            if bind_vars and any(v not in params for v in bind_vars):
                continue
        result.append(line)
    return "\n".join(result)
