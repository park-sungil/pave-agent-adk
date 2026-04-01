"""Oracle DB client for PPA data queries.

In production, connects to Oracle via oracledb.
Currently uses mock data for development.
"""

from __future__ import annotations

import logging
from typing import Any

from pave_lib import settings

logger = logging.getLogger(__name__)

# Mock data for development
_MOCK_PPA_DATA: list[dict[str, Any]] = [
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.28, "PARAM_UNIT": "V", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.22, "PARAM_UNIT": "V", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.35, "PARAM_UNIT": "V", "CORNER": "SS", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 850e-6, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 1020e-6, "PARAM_UNIT": "A", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 680e-6, "PARAM_UNIT": "A", "CORNER": "SS", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 5e-9, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 15e-9, "PARAM_UNIT": "A", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 1e-9, "PARAM_UNIT": "A", "CORNER": "SS", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "NAND2D1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.30, "PARAM_UNIT": "V", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "NAND2D1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 720e-6, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "NAND2D1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 4e-9, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-01-15"},
    # Version v1.1 data for trend analysis
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.1", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.26, "PARAM_UNIT": "V", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-04-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.1", "PARAM_NAME": "ION", "PARAM_VALUE": 900e-6, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-04-15"},
    {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.1", "PARAM_NAME": "IOFF", "PARAM_VALUE": 7e-9, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75, "MEASURE_DATE": "2025-04-15"},
]

_MOCK_VERSION_DATA: list[dict[str, Any]] = [
    {"PROCESS_NODE": "N5", "VERSION": "v1.0", "RELEASE_DATE": "2025-01-10", "STATUS": "RELEASED", "DESCRIPTION": "Initial N5 PDK release"},
    {"PROCESS_NODE": "N5", "VERSION": "v1.1", "RELEASE_DATE": "2025-04-10", "STATUS": "RELEASED", "DESCRIPTION": "N5 PDK update with optimized VTH"},
    {"PROCESS_NODE": "N3", "VERSION": "v0.9", "RELEASE_DATE": "2025-03-01", "STATUS": "DRAFT", "DESCRIPTION": "N3 PDK draft release"},
]


def _use_mock() -> bool:
    """Check if we should use mock data (no real Oracle connection configured)."""
    return not settings.ORACLE_PASSWORD


def execute_query(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts.

    Uses mock data when Oracle is not configured.
    """
    if _use_mock():
        return _execute_mock(sql, params)
    return _execute_oracle(sql, params)


def _execute_oracle(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute query against real Oracle DB."""
    import oracledb

    with oracledb.connect(
        user=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        dsn=settings.ORACLE_DSN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _execute_mock(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Filter mock data based on SQL template and params."""
    logger.info("Using mock data (Oracle not configured)")
    sql_upper = sql.upper()

    if "V_VERSION_INFO" in sql_upper:
        source = _MOCK_VERSION_DATA
    else:
        source = _MOCK_PPA_DATA

    results = source
    for key, value in params.items():
        if value is None:
            continue
        col = key.upper()
        if isinstance(value, list):
            results = [r for r in results if r.get(col) in value]
        else:
            results = [r for r in results if r.get(col) == value]

    return results
