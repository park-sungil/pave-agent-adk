"""Sandboxed Python code executor for analysis tasks.

Executes LLM-generated analysis code in a restricted environment
with access to data analysis libraries only.
"""

from __future__ import annotations

import base64
import io
import logging
import traceback
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_MODULES = {
    "pandas", "numpy", "scipy", "matplotlib", "math", "statistics",
    "collections", "itertools", "functools", "operator", "json",
    "base64", "io", "datetime",
}


def execute(code: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    """Execute analysis code in a sandboxed environment.

    Args:
        code: Python code string to execute. Must produce `result` dict
              and optionally `charts` list.
        data: Input data as list of dicts (from query_data).

    Returns:
        Dict with 'result' (analysis output) and 'charts' (list of base64 PNGs).
        On error, returns dict with 'error' key.
    """
    # Set up restricted namespace
    namespace: dict[str, Any] = {
        "__builtins__": _safe_builtins(),
        "data": data,
    }

    # Pre-import allowed modules
    try:
        import pandas as pd
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from scipy import stats

        namespace.update({
            "pd": pd,
            "np": np,
            "plt": plt,
            "stats": stats,
            "base64": base64,
            "BytesIO": io.BytesIO,
        })
    except ImportError as e:
        logger.warning("Optional analysis dependency not available: %s", e)

    # Initialize output variables
    namespace["result"] = {}
    namespace["charts"] = []

    try:
        exec(code, namespace)  # noqa: S102
        return {
            "result": namespace.get("result", {}),
            "charts": namespace.get("charts", []),
        }
    except Exception:
        error_msg = traceback.format_exc()
        logger.error("Code execution failed:\n%s", error_msg)
        return {"error": error_msg}


def _safe_builtins() -> dict[str, Any]:
    """Return a restricted set of builtins."""
    import builtins

    allowed = {
        "abs", "all", "any", "bool", "dict", "enumerate", "filter", "float",
        "format", "frozenset", "getattr", "hasattr", "hash", "int", "isinstance",
        "issubclass", "iter", "len", "list", "map", "max", "min", "next",
        "object", "pow", "print", "range", "repr", "reversed", "round", "set",
        "slice", "sorted", "str", "sum", "tuple", "type", "zip",
        "True", "False", "None",
    }
    return {k: getattr(builtins, k) for k in allowed if hasattr(builtins, k)}
