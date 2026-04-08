"""DB client — Oracle in production, SQLite mock in development."""

from __future__ import annotations

import datetime
import logging
from typing import Any

from pave_agent import settings

logger = logging.getLogger(__name__)


def _use_mock() -> bool:
    return not settings.ORACLE_PASSWORD


def execute_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts.

    datetime values are converted to ISO strings for JSON serialization.
    """
    if _use_mock():
        from pave_agent.db import mock_db
        rows = mock_db.query(sql, params)
    else:
        rows = _execute_oracle(sql, params or {})
    return [
        {k: _serialize_datetime(v) for k, v in row.items()}
        for row in rows
    ]


def _serialize_datetime(value: Any) -> Any:
    """Convert datetime to ISO string."""
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    return value


_oracle_client_initialized = False


def _ensure_thick_mode() -> None:
    """Initialize Oracle thick mode once."""
    global _oracle_client_initialized
    if not _oracle_client_initialized:
        import oracledb
        oracledb.init_oracle_client()
        _oracle_client_initialized = True


def _clob_to_string_handler(cursor, metadata):
    """Fetch CLOB/BLOB columns as str/bytes instead of LOB objects.

    LOB objects become unusable once the cursor/connection closes,
    so convert at fetch time.
    """
    import oracledb
    if metadata.type_code == oracledb.DB_TYPE_CLOB:
        return cursor.var(oracledb.DB_TYPE_LONG, arraysize=cursor.arraysize)
    if metadata.type_code == oracledb.DB_TYPE_BLOB:
        return cursor.var(oracledb.DB_TYPE_LONG_RAW, arraysize=cursor.arraysize)
    return None


def _execute_oracle(sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    """Execute query against real Oracle DB (thick mode)."""
    import oracledb

    _ensure_thick_mode()

    with oracledb.connect(
        user=settings.ORACLE_USER,
        password=settings.ORACLE_PASSWORD,
        dsn=settings.ORACLE_DSN,
    ) as conn:
        conn.outputtypehandler = _clob_to_string_handler
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
