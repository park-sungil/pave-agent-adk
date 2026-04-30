"""Unit tests for query_data._version_match — component-aware version matching."""

import pytest

from pave_agent.tools.query_data import _version_match


@pytest.mark.parametrize("stored, user, expected", [
    # Happy path — short user form matches zero-padded stored
    ("V1.0.0.0", "v1.0", True),
    ("V1.0.0.0", "V1.0", True),       # case insensitive
    ("V1.0.0.0", "1.0", True),         # leading 'v' optional
    ("V0.9.0.0", "v0.9", True),
    # Exact full-form
    ("V1.0.0.0", "v1.0.0.0", True),
    # NOT matches: different patch / minor / etc.
    ("V1.0.5.0", "v1.0", False),       # 1.0.5.0 ≠ zero-padded 1.0
    ("V1.1.0.0", "v1.0", False),
    ("V0.9.5.0", "v0.9", False),
    # Edge case: prevents string-prefix accidents (1.0 vs 1.05)
    ("V1.05.0.0", "v1.0", False),
    # User more specific than stored → no match
    ("V1.0", "v1.0.0.0", False),
])
def test_version_match(stored, user, expected):
    assert _version_match(stored, user) is expected


def test_none_stored_returns_false():
    assert _version_match(None, "v1.0") is False
