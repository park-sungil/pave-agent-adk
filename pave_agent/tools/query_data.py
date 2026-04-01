"""query_data tool: Pure code SQL query builder and executor.

No LLM calls. Assembles SQL from templates based on entities
extracted by the orchestrator, executes against Oracle DB.
"""

from __future__ import annotations

import logging
from typing import Any

from pave_agent.db import oracle_client

logger = logging.getLogger(__name__)

# SQL templates loaded from SQL Skill definition
_TEMPLATES = {
    "single_cell": """
        SELECT PARAM_NAME, PARAM_VALUE, PARAM_UNIT, CORNER, TEMPERATURE, VOLTAGE
        FROM V_PPA_DATA
        WHERE PROCESS_NODE = :process_node
          AND CELL_NAME = :cell_name
          {version_clause}
        ORDER BY PARAM_NAME, CORNER
    """,
    "compare_cells": """
        SELECT CELL_NAME, PARAM_NAME, PARAM_VALUE, PARAM_UNIT, CORNER
        FROM V_PPA_DATA
        WHERE PROCESS_NODE = :process_node
          AND CELL_NAME IN ({cell_placeholders})
          {version_clause}
          {param_clause}
        ORDER BY CELL_NAME, PARAM_NAME
    """,
    "trend": """
        SELECT VERSION, PARAM_NAME, PARAM_VALUE, MEASURE_DATE
        FROM V_PPA_DATA
        WHERE PROCESS_NODE = :process_node
          AND CELL_NAME = :cell_name
          {param_clause}
        ORDER BY MEASURE_DATE, PARAM_NAME
    """,
    "versions": """
        SELECT VERSION, RELEASE_DATE, STATUS, DESCRIPTION
        FROM V_VERSION_INFO
        WHERE PROCESS_NODE = :process_node
          {status_clause}
        ORDER BY RELEASE_DATE DESC
    """,
}

# Entity name mapping (Korean/English -> DB column values)
_PARAM_MAP = {
    "vth": "VTH", "문턱전압": "VTH", "threshold": "VTH",
    "ion": "ION", "온전류": "ION", "on current": "ION",
    "ioff": "IOFF", "누설전류": "IOFF", "leakage": "IOFF", "off current": "IOFF",
    "cgate": "CGATE", "게이트캐패시턴스": "CGATE", "gate cap": "CGATE",
}


def _normalize_param(name: str) -> str:
    """Normalize parameter name to DB column value."""
    return _PARAM_MAP.get(name.lower().replace(" ", ""), name.upper())


def query_data(
    process_node: str,
    cell_name: str | None = None,
    cell_names: list[str] | None = None,
    parameters: list[str] | None = None,
    version: str | None = None,
    query_type: str = "single_cell",
) -> dict[str, Any]:
    """PPA 데이터를 Oracle DB에서 조회한다.

    오케스트레이터가 추출한 엔티티를 기반으로 SQL을 조립하고 실행한다.
    LLM 호출 없이 순수 코드로 동작한다.

    Args:
        process_node: 공정 노드 (e.g., "N5", "N3").
        cell_name: 단일 셀 이름 (e.g., "INVD1"). single_cell, trend 쿼리에 사용.
        cell_names: 셀 이름 목록. compare_cells 쿼리에 사용.
        parameters: 조회할 파라미터 목록 (e.g., ["VTH", "ION"]). None이면 전체.
        version: PDK 버전 (e.g., "v1.0"). None이면 전체 버전.
        query_type: 쿼리 유형. "single_cell", "compare_cells", "trend", "versions" 중 하나.

    Returns:
        {"data": [...], "count": int, "query_type": str} 형태의 조회 결과.
        오류 시 {"error": str} 반환.
    """
    try:
        params: dict[str, Any] = {"process_node": process_node}

        if query_type == "single_cell":
            if not cell_name:
                return {"error": "cell_name is required for single_cell query"}
            params["cell_name"] = cell_name
            version_clause = "AND VERSION = :version" if version else ""
            if version:
                params["version"] = version
            sql = _TEMPLATES["single_cell"].format(version_clause=version_clause)

        elif query_type == "compare_cells":
            names = cell_names or ([cell_name] if cell_name else [])
            if not names:
                return {"error": "cell_names is required for compare_cells query"}
            # For mock: pass as list param
            params["cell_name"] = names
            version_clause = "AND VERSION = :version" if version else ""
            if version:
                params["version"] = version
            param_clause = ""
            if parameters:
                norm_params = [_normalize_param(p) for p in parameters]
                params["param_name"] = norm_params
                param_clause = "AND PARAM_NAME IN (:param_names)"
            sql = _TEMPLATES["compare_cells"].format(
                cell_placeholders=":cell_names",
                version_clause=version_clause,
                param_clause=param_clause,
            )

        elif query_type == "trend":
            if not cell_name:
                return {"error": "cell_name is required for trend query"}
            params["cell_name"] = cell_name
            param_clause = ""
            if parameters:
                norm_params = [_normalize_param(p) for p in parameters]
                params["param_name"] = norm_params
                param_clause = "AND PARAM_NAME IN (:param_names)"
            sql = _TEMPLATES["trend"].format(param_clause=param_clause)

        elif query_type == "versions":
            status_clause = ""
            sql = _TEMPLATES["versions"].format(status_clause=status_clause)

        else:
            return {"error": f"Unknown query_type: {query_type}"}

        results = oracle_client.execute_query(sql, params)

        return {
            "data": results,
            "count": len(results),
            "query_type": query_type,
        }

    except Exception as e:
        logger.error("query_data failed: %s", e, exc_info=True)
        return {"error": str(e)}
