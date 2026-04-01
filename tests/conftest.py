"""Common test fixtures."""

import pytest


@pytest.fixture
def sample_ppa_data():
    """Sample PPA data matching mock Oracle data format."""
    return [
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.28, "PARAM_UNIT": "V", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.22, "PARAM_UNIT": "V", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "VTH", "PARAM_VALUE": 0.35, "PARAM_UNIT": "V", "CORNER": "SS", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 850e-6, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "ION", "PARAM_VALUE": 1020e-6, "PARAM_UNIT": "A", "CORNER": "FF", "TEMPERATURE": 25, "VOLTAGE": 0.75},
        {"PROCESS_NODE": "N5", "CELL_NAME": "INVD1", "VERSION": "v1.0", "PARAM_NAME": "IOFF", "PARAM_VALUE": 5e-9, "PARAM_UNIT": "A", "CORNER": "TT", "TEMPERATURE": 25, "VOLTAGE": 0.75},
    ]
