"""Module-level in-memory cache for DB table data."""

from __future__ import annotations

from typing import Any

_cache: dict[str, list[dict[str, Any]]] = {}


def has(table: str) -> bool:
    return table in _cache


def get(table: str) -> list[dict[str, Any]]:
    return _cache.get(table, [])


def put(table: str, data: list[dict[str, Any]]) -> None:
    _cache[table] = data


def clear() -> None:
    _cache.clear()
