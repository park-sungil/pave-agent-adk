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
        오류 시 {"error": str}.
    """
    filters = filters or {}

    try:
        # --- cached tables: full scan + Python filter ---
        cache_table = _CACHE_TABLES.get(query_type)
        if cache_table:
            cache_key = f"_cache_{cache_table}"
            if cache_key not in tool_context.state:
                tool_context.state[cache_key] = oracle_client.execute_query(
                    f"SELECT * FROM {cache_table}"
                )
            all_rows = tool_context.state[cache_key]
            results = _filter_rows(all_rows, filters)
            return {"data": results, "count": len(results), "query_type": query_type}

        # --- SQL template queries ---
        template = _TEMPLATES.get(query_type)
        if template is None:
            return {"error": f"Unknown query_type: {query_type}"}

        params, format_args = _build_params(template, filters)
        sql = template.format(**format_args)
        logger.info("[SQL] query_type=%s\n%s\nparams=%s", query_type, sql, params)
        results = oracle_client.execute_query(sql, params)

        return {
            "data": results,
            "count": len(results),
            "query_type": query_type,
        }

    except Exception as e:
        logger.error("query_data failed: %s", e, exc_info=True)
        return {"error": str(e)}


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

    # Handle {pdk_clause} placeholder
    if "{pdk_clause}" in template:
        if "pdk_id" in params:
            format_args["pdk_clause"] = "AND d.PDK_ID = :pdk_id"
        else:
            format_args["pdk_clause"] = "AND v.IS_GOLDEN = 1"

    # Handle {cell_placeholders} — if not already set by list expansion
    if "{cell_placeholders}" in template and "cell_placeholders" not in format_args:
        if "cells" in filters and isinstance(filters["cells"], list):
            placeholders = ", ".join(f":cells_{i}" for i in range(len(filters["cells"])))
            for i, v in enumerate(filters["cells"]):
                params[f"cells_{i}"] = v
            format_args["cell_placeholders"] = placeholders
        elif "cell" in params:
            # single cell for compare
            params["cell_0"] = params.pop("cell")
            format_args["cell_placeholders"] = ":cell_0"

    return params, format_args
