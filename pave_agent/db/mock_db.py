"""SQLite mock database for development.

Creates and seeds a SQLite DB matching the real Oracle schema
(antsdb.PAVE_PDK_VERSION_VIEW, antsdb.PAVE_PPA_DATA_VIEW).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

_DB_PATH = Path(__file__).parent / "mock.db"
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        exists = _DB_PATH.exists()
        _conn = sqlite3.connect(str(_DB_PATH))
        _conn.row_factory = sqlite3.Row
        if not exists:
            _seed(_conn)
    return _conn


def query(sql: str, params: dict | None = None) -> list[dict]:
    """Execute SQL and return results as list of dicts."""
    conn = _get_conn()
    cursor = conn.execute(sql, params or {})
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _seed(conn: sqlite3.Connection) -> None:
    """Create tables and insert seed data."""
    conn.executescript(_DDL)
    conn.executemany(
        """INSERT INTO PAVE_PDK_VERSION_VIEW
           (PAVE_PDK_ID, PROCESS, PROJECT, PROJECT_NAME, MASK, DK_GDS,
            IS_GOLDEN, VDD_NOMINAL, HSPICE, LVS, PEX, CREATED_AT, CREATED_BY)
           VALUES (:PAVE_PDK_ID, :PROCESS, :PROJECT, :PROJECT_NAME, :MASK, :DK_GDS,
                   :IS_GOLDEN, :VDD_NOMINAL, :HSPICE, :LVS, :PEX, :CREATED_AT, :CREATED_BY)""",
        _SEED_PDK_VERSION,
    )
    conn.executemany(
        """INSERT INTO PAVE_PPA_DATA_VIEW
           (PDK_ID, CELL, DS, CORNER, TEMP, VDD, VTH, WNS, WNS_VAL, CH, CH_TYPE,
            FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, ACREFF_KOHM, S_POWER, IDDQ_NA)
           VALUES (:PDK_ID, :CELL, :DS, :CORNER, :TEMP, :VDD, :VTH, :WNS, :WNS_VAL, :CH, :CH_TYPE,
                   :FREQ_GHZ, :D_POWER, :D_ENERGY, :ACCEFF_FF, :ACREFF_KOHM, :S_POWER, :IDDQ_NA)""",
        _SEED_PPA_DATA,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE PAVE_PDK_VERSION_VIEW (
    PAVE_PDK_ID  INTEGER PRIMARY KEY,
    PROCESS      TEXT NOT NULL,
    PROJECT      TEXT NOT NULL,
    PROJECT_NAME TEXT NOT NULL,
    MASK         TEXT NOT NULL,
    DK_GDS       TEXT NOT NULL,
    IS_GOLDEN    INTEGER NOT NULL DEFAULT 0,
    VDD_NOMINAL  REAL,
    HSPICE       TEXT,
    LVS          TEXT,
    PEX          TEXT,
    CREATED_AT   TEXT,
    CREATED_BY   TEXT
);

CREATE TABLE PAVE_PPA_DATA_VIEW (
    PDK_ID       INTEGER NOT NULL REFERENCES PAVE_PDK_VERSION_VIEW(PAVE_PDK_ID),
    CELL         TEXT NOT NULL,
    DS           TEXT NOT NULL,
    CORNER       TEXT NOT NULL,
    TEMP         INTEGER NOT NULL,
    VDD          REAL NOT NULL,
    VTH          TEXT NOT NULL,
    WNS          TEXT,
    WNS_VAL      REAL,
    CH           TEXT,
    CH_TYPE      TEXT,
    FREQ_GHZ     REAL,
    D_POWER      REAL,
    D_ENERGY     REAL,
    ACCEFF_FF    REAL,
    ACREFF_KOHM  REAL,
    S_POWER      REAL,
    IDDQ_NA      REAL
);

CREATE INDEX idx_ppa_pdk_id ON PAVE_PPA_DATA_VIEW(PDK_ID);
"""

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

_SEED_PDK_VERSION = [
    # LN04LPP / Solomon
    {"PAVE_PDK_ID": 881, "PROCESS": "LN04LPP", "PROJECT": "S5E9945", "PROJECT_NAME": "Solomon", "MASK": "EVT0", "DK_GDS": "Solomon EVT0", "IS_GOLDEN": 0, "VDD_NOMINAL": 0.75, "HSPICE": "V0.9.0.0", "LVS": "V0.9.0.0", "PEX": "V0.9.0.0", "CREATED_AT": "2025-06-01 10:00:00", "CREATED_BY": "si0807.park"},
    {"PAVE_PDK_ID": 882, "PROCESS": "LN04LPP", "PROJECT": "S5E9945", "PROJECT_NAME": "Solomon", "MASK": "EVT0", "DK_GDS": "Solomon EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.75, "HSPICE": "V0.9.2.0", "LVS": "V0.9.2.0", "PEX": "V0.9.2.0", "CREATED_AT": "2025-07-15 14:30:00", "CREATED_BY": "si0807.park"},
    {"PAVE_PDK_ID": 883, "PROCESS": "LN04LPP", "PROJECT": "S5E9945", "PROJECT_NAME": "Solomon", "MASK": "EVT1", "DK_GDS": "Solomon EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.75, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-09-20 09:15:00", "CREATED_BY": "si0807.park"},
    # LN04LPP / Thetis
    {"PAVE_PDK_ID": 900, "PROCESS": "LN04LPP", "PROJECT": "S5E9955", "PROJECT_NAME": "Thetis", "MASK": "EVT0", "DK_GDS": "Thetis EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.2.0", "LVS": "V0.9.2.0", "PEX": "V0.9.2.0", "CREATED_AT": "2025-08-01 11:00:00", "CREATED_BY": "jh.kim"},
    {"PAVE_PDK_ID": 901, "PROCESS": "LN04LPP", "PROJECT": "S5E9955", "PROJECT_NAME": "Thetis", "MASK": "EVT1", "DK_GDS": "Thetis EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-10-10 16:00:00", "CREATED_BY": "jh.kim"},
    # LN04LPE / Ulysses
    {"PAVE_PDK_ID": 910, "PROCESS": "LN04LPE", "PROJECT": "S5E9965", "PROJECT_NAME": "Ulysses", "MASK": "EVT0", "DK_GDS": "Ulysses EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.75, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-11-05 08:45:00", "CREATED_BY": "si0807.park"},
    {"PAVE_PDK_ID": 911, "PROCESS": "LN04LPE", "PROJECT": "S5E9965", "PROJECT_NAME": "Ulysses", "MASK": "EVT1", "DK_GDS": "Ulysses EVT1", "IS_GOLDEN": 0, "VDD_NOMINAL": 0.75, "HSPICE": "V1.0.0.0", "LVS": "V1.0.0.0", "PEX": "V1.0.0.0", "CREATED_AT": "2026-01-12 13:20:00", "CREATED_BY": "si0807.park"},
    {"PAVE_PDK_ID": 912, "PROCESS": "LN04LPE", "PROJECT": "S5E9965", "PROJECT_NAME": "Ulysses", "MASK": "EVT1", "DK_GDS": "Ulysses EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.75, "HSPICE": "V1.0.0.0", "LVS": "V1.0.0.0", "PEX": "V1.0.0.0", "CREATED_AT": "2026-02-01 10:00:00", "CREATED_BY": "si0807.park"},
    # SF3 / Vanguard
    {"PAVE_PDK_ID": 920, "PROCESS": "SF3", "PROJECT": "S5E9975", "PROJECT_NAME": "Vanguard", "MASK": "EVT0", "DK_GDS": "Vanguard EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2026-01-20 09:00:00", "CREATED_BY": "jh.kim"},
]

_SEED_PPA_DATA = [
    # --- PDK 882 (Solomon EVT0, golden) ---
    # INV D1, SLVT, TT/FF/SS @ 25C, 0.75V
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.82, "D_POWER": 0.0312, "D_ENERGY": 6.48e-15, "ACCEFF_FF": 11.52, "ACREFF_KOHM": 1.85, "S_POWER": 0.00185, "IDDQ_NA": 2.47},
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "FF",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 5.64, "D_POWER": 0.0365, "D_ENERGY": 6.47e-15, "ACCEFF_FF": 11.51, "ACREFF_KOHM": 1.58, "S_POWER": 0.00412, "IDDQ_NA": 5.49},
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "SS",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.91, "D_POWER": 0.0253, "D_ENERGY": 6.47e-15, "ACCEFF_FF": 11.51, "ACREFF_KOHM": 2.28, "S_POWER": 0.00072, "IDDQ_NA": 0.96},
    # INV D1, SLVT, TT @ 125C (high temp — leakage jump)
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 125, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.55, "D_POWER": 0.0295, "D_ENERGY": 6.48e-15, "ACCEFF_FF": 11.52, "ACREFF_KOHM": 1.96, "S_POWER": 0.0285, "IDDQ_NA": 38.0},
    # INV D1, SLVT, TT @ -25C (low temp)
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": -25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.90, "D_POWER": 0.0317, "D_ENERGY": 6.47e-15, "ACCEFF_FF": 11.51, "ACREFF_KOHM": 1.82, "S_POWER": 0.00032, "IDDQ_NA": 0.43},
    # INV D1, LVT (higher Vth → slower, lower leakage)
    {"PDK_ID": 882, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "LVT",  "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.15, "D_POWER": 0.0285, "D_ENERGY": 6.87e-15, "ACCEFF_FF": 12.21, "ACREFF_KOHM": 2.15, "S_POWER": 0.00098, "IDDQ_NA": 1.31},
    # INV D4 (higher drive strength — ~4x power/area)
    {"PDK_ID": 882, "CELL": "INV", "DS": "D4", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.78, "D_POWER": 0.1248, "D_ENERGY": 2.61e-14, "ACCEFF_FF": 46.40, "ACREFF_KOHM": 0.46, "S_POWER": 0.00740, "IDDQ_NA": 9.87},
    # ND2 D1, TT/FF @ 25C
    {"PDK_ID": 882, "CELL": "ND2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.65, "D_POWER": 0.0298, "D_ENERGY": 8.16e-15, "ACCEFF_FF": 14.51, "ACREFF_KOHM": 2.44, "S_POWER": 0.00205, "IDDQ_NA": 2.73},
    {"PDK_ID": 882, "CELL": "ND2", "DS": "D1", "CORNER": "FF",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.28, "D_POWER": 0.0349, "D_ENERGY": 8.15e-15, "ACCEFF_FF": 14.49, "ACREFF_KOHM": 2.08, "S_POWER": 0.00456, "IDDQ_NA": 6.08},
    # NR2 D1, TT @ 25C
    {"PDK_ID": 882, "CELL": "NR2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.12, "D_POWER": 0.0275, "D_ENERGY": 8.81e-15, "ACCEFF_FF": 15.67, "ACREFF_KOHM": 2.86, "S_POWER": 0.00220, "IDDQ_NA": 2.93},

    # --- PDK 883 (Solomon EVT1, golden) — improved freq vs EVT0 ---
    {"PDK_ID": 883, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 5.01, "D_POWER": 0.0324, "D_ENERGY": 6.47e-15, "ACCEFF_FF": 11.50, "ACREFF_KOHM": 1.78, "S_POWER": 0.00178, "IDDQ_NA": 2.37},
    {"PDK_ID": 883, "CELL": "INV", "DS": "D1", "CORNER": "FF",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 5.85, "D_POWER": 0.0378, "D_ENERGY": 6.46e-15, "ACCEFF_FF": 11.49, "ACREFF_KOHM": 1.52, "S_POWER": 0.00398, "IDDQ_NA": 5.31},
    {"PDK_ID": 883, "CELL": "INV", "DS": "D1", "CORNER": "SS",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.08, "D_POWER": 0.0264, "D_ENERGY": 6.47e-15, "ACCEFF_FF": 11.50, "ACREFF_KOHM": 2.18, "S_POWER": 0.00068, "IDDQ_NA": 0.91},
    {"PDK_ID": 883, "CELL": "ND2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.81, "D_POWER": 0.0311, "D_ENERGY": 8.16e-15, "ACCEFF_FF": 14.51, "ACREFF_KOHM": 2.34, "S_POWER": 0.00197, "IDDQ_NA": 2.63},
    {"PDK_ID": 883, "CELL": "NR2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.28, "D_POWER": 0.0289, "D_ENERGY": 8.80e-15, "ACCEFF_FF": 15.64, "ACREFF_KOHM": 2.72, "S_POWER": 0.00210, "IDDQ_NA": 2.80},

    # --- PDK 900 (Thetis EVT0, golden, VDD=0.72V, CH148/uHD) ---
    {"PDK_ID": 900, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.72, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH148", "CH_TYPE": "uHD", "FREQ_GHZ": 4.45, "D_POWER": 0.0278, "D_ENERGY": 6.25e-15, "ACCEFF_FF": 12.05, "ACREFF_KOHM": 2.01, "S_POWER": 0.00165, "IDDQ_NA": 2.29},
    {"PDK_ID": 900, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 125, "VDD": 0.72, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH148", "CH_TYPE": "uHD", "FREQ_GHZ": 4.18, "D_POWER": 0.0261, "D_ENERGY": 6.25e-15, "ACCEFF_FF": 12.05, "ACREFF_KOHM": 2.14, "S_POWER": 0.0252, "IDDQ_NA": 35.0},
    {"PDK_ID": 900, "CELL": "ND2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.72, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH148", "CH_TYPE": "uHD", "FREQ_GHZ": 3.38, "D_POWER": 0.0265, "D_ENERGY": 7.84e-15, "ACCEFF_FF": 15.11, "ACREFF_KOHM": 2.65, "S_POWER": 0.00183, "IDDQ_NA": 2.54},
    {"PDK_ID": 900, "CELL": "NR2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.72, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH148", "CH_TYPE": "uHD", "FREQ_GHZ": 2.88, "D_POWER": 0.0242, "D_ENERGY": 8.40e-15, "ACCEFF_FF": 16.20, "ACREFF_KOHM": 3.11, "S_POWER": 0.00198, "IDDQ_NA": 2.75},

    # --- PDK 910 (Ulysses EVT0, golden) ---
    {"PDK_ID": 910, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 4.70, "D_POWER": 0.0305, "D_ENERGY": 6.49e-15, "ACCEFF_FF": 11.54, "ACREFF_KOHM": 1.90, "S_POWER": 0.00190, "IDDQ_NA": 2.53},
    {"PDK_ID": 910, "CELL": "ND2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.75, "VTH": "SLVT", "WNS": "N3", "WNS_VAL": 25, "CH": "CH168", "CH_TYPE": "HD", "FREQ_GHZ": 3.55, "D_POWER": 0.0290, "D_ENERGY": 8.17e-15, "ACCEFF_FF": 14.53, "ACREFF_KOHM": 2.51, "S_POWER": 0.00210, "IDDQ_NA": 2.80},

    # --- PDK 920 (Vanguard EVT0, golden, SF3 process) ---
    {"PDK_ID": 920, "CELL": "INV", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.72, "VTH": "SLVT", "WNS": "N4", "WNS_VAL": 35, "CH": "CH200", "CH_TYPE": "HP", "FREQ_GHZ": 3.95, "D_POWER": 0.0258, "D_ENERGY": 6.53e-15, "ACCEFF_FF": 12.59, "ACREFF_KOHM": 2.26, "S_POWER": 0.00155, "IDDQ_NA": 2.15},
    {"PDK_ID": 920, "CELL": "ND2", "DS": "D1", "CORNER": "TT",   "TEMP": 25, "VDD": 0.72, "VTH": "SLVT", "WNS": "N4", "WNS_VAL": 35, "CH": "CH200", "CH_TYPE": "HP", "FREQ_GHZ": 2.98, "D_POWER": 0.0245, "D_ENERGY": 8.22e-15, "ACCEFF_FF": 15.85, "ACREFF_KOHM": 3.00, "S_POWER": 0.00172, "IDDQ_NA": 2.39},
]
