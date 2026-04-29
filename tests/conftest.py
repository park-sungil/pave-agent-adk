"""Shared test fixtures.

`mock_db_reset` autouse fixture forces the SQLite mock DB path (by clearing
ORACLE_PASSWORD) and deletes any cached mock.db so each test session sees
deterministic seeded data.
"""

import os

# Force mock SQLite DB before pave_agent.settings imports.
# load_dotenv inside settings.py won't override an already-set env var.
os.environ["ORACLE_PASSWORD"] = ""

from pathlib import Path

import pytest

from pave_agent import settings
from pave_agent.db import mock_db
from pave_agent.tools.query_data import load_default_wns_config, load_versions

# Belt and suspenders: if .env was loaded before this conftest set the env,
# also clear the cached attribute on the settings module.
settings.ORACLE_PASSWORD = ""


@pytest.fixture(scope="session", autouse=True)
def _reset_mock_db():
    """Delete cached SQLite mock so each session generates fresh deterministic data."""
    db_path = Path(mock_db._DB_PATH)
    if mock_db._conn is not None:
        mock_db._conn.close()
        mock_db._conn = None
    if db_path.exists():
        db_path.unlink()
    yield


class FakeToolContext:
    """Minimal stand-in for ADK ToolContext exposing a writable .state dict."""

    def __init__(self) -> None:
        self.state: dict = {}


@pytest.fixture
def fake_tool_context() -> FakeToolContext:
    return FakeToolContext()


@pytest.fixture
def ppa_loaded_state(fake_tool_context: FakeToolContext) -> FakeToolContext:
    """FakeToolContext with PDK versions + default WNS config pre-loaded.

    Mirrors agent.py:_init_state, which runs as before_agent_callback in production.
    """
    load_versions(fake_tool_context.state)
    load_default_wns_config(fake_tool_context.state)
    return fake_tool_context


@pytest.fixture
def sample_ppa_data():
    """Legacy fixture for sandbox executor tests (test_analyze.py)."""
    return [
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.28, "PARAM_UNIT": "V", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.22, "PARAM_UNIT": "V", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.35, "PARAM_UNIT": "V", "CORNER": "SS", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 850e-6, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 1020e-6, "PARAM_UNIT": "A", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 5e-9, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
    ]
