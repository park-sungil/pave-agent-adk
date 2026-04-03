"""DB client — Oracle in production, SQLite mock in development."""

from __future__ import annotations

import logging
from typing import Any

from common import settings

logger = logging.getLogger(__name__)


def _use_mock() -> bool:
    return not settings.ORACLE_PASSWORD


def execute_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts."""
    if _use_mock():
        from common.db import mock_db
        return mock_db.query(sql, params)
    return _execute_oracle(sql, params or {})


_oracle_client_initialized = False


def _ensure_thick_mode() -> None:
    """Initialize Oracle thick mode once."""
    global _oracle_client_initialized
    if not _oracle_client_initialized:
        import oracledb
        oracledb.init_oracle_client()
        _oracle_client_initialized = True


def _execute_oracle(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute query against real Oracle DB (thick mode)."""
    import oracledb

    _ensure_thick_mode()

    with oracledb.connect(
        user=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        dsn=settings.ORACLE_DSN,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
