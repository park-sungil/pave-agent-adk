"""SQLite mock database for development.

Creates and seeds a SQLite DB matching the real Oracle schema
(antsdb.PAVE_PDK_VERSION_VIEW, antsdb.PAVE_PPA_DATA_VIEW).

PPA data is generated programmatically as a full cross product of
all parameter combinations with physically plausible measurement values.
"""

from __future__ import annotations

import json
import math
import random
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
    # Strip schema prefixes — SQLite doesn't support schema-qualified names
    sql = sql.replace("ANTSDB.", "").replace("AT9.", "")
    # Translate Oracle FETCH FIRST to SQLite LIMIT
    sql = sql.replace("FETCH FIRST 1 ROW ONLY", "LIMIT 1")
    conn = _get_conn()
    cursor = conn.execute(sql, params or {})
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _seed(conn: sqlite3.Connection) -> None:
    """Create tables and insert seed data."""
    conn.executescript(_DDL)
    conn.executemany(
        """INSERT INTO PAVE_PDK_VERSION_VIEW
           (PDK_ID, PROCESS, PROJECT, PROJECT_NAME, MASK, DK_GDS,
            IS_GOLDEN, VDD_NOMINAL, HSPICE, LVS, PEX, CREATED_AT, CREATED_BY)
           VALUES (:PDK_ID, :PROCESS, :PROJECT, :PROJECT_NAME, :MASK, :DK_GDS,
                   :IS_GOLDEN, :VDD_NOMINAL, :HSPICE, :LVS, :PEX, :CREATED_AT, :CREATED_BY)""",
        _SEED_PDK_VERSION,
    )
    ppa_rows = _generate_ppa_data()
    conn.executemany(
        """INSERT INTO PAVE_PPA_DATA_VIEW
           (PDK_ID, CELL, DS, CORNER, TEMP, VDD, VDD_TYPE, VTH, WNS, WNS_VAL, CH, CH_TYPE,
            FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, ACREFF_KOHM, S_POWER, IDDQ_NA)
           VALUES (:PDK_ID, :CELL, :DS, :CORNER, :TEMP, :VDD, :VDD_TYPE, :VTH, :WNS, :WNS_VAL, :CH, :CH_TYPE,
                   :FREQ_GHZ, :D_POWER, :D_ENERGY, :ACCEFF_FF, :ACREFF_KOHM, :S_POWER, :IDDQ_NA)""",
        ppa_rows,
    )
    conn.executemany(
        """INSERT INTO PDKPAS_CONFIG_JSON_FAV
           (ID, CREATED_AT, CREATED_BY, CONFIG_DATA)
           VALUES (:ID, :CREATED_AT, :CREATED_BY, :CONFIG_DATA)""",
        _SEED_CONFIG,
    )
    conn.commit()


# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE PAVE_PDK_VERSION_VIEW (
    PDK_ID  INTEGER PRIMARY KEY,
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
    PDK_ID       INTEGER NOT NULL REFERENCES PAVE_PDK_VERSION_VIEW(PDK_ID),
    CELL         TEXT NOT NULL,
    DS           TEXT NOT NULL,
    CORNER       TEXT NOT NULL,
    TEMP         TEXT NOT NULL,
    VDD          TEXT NOT NULL,
    VDD_TYPE     TEXT,
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

CREATE TABLE PDKPAS_CONFIG_JSON_FAV (
    ID         INTEGER PRIMARY KEY,
    CREATED_AT TEXT,
    CREATED_BY TEXT,
    CONFIG_DATA TEXT
);
"""

# ---------------------------------------------------------------------------
# Config seed data (default WNS per project, ch_type)
# ---------------------------------------------------------------------------

_SEED_CONFIG = [
    {
        "ID": 1,
        "CREATED_AT": "2026-04-01 00:00:00",
        "CREATED_BY": "admin",
        "CONFIG_DATA": json.dumps({
            "ppa_summary_default_wns": [
                # Solomon EVT1: HP and HD only — uHD missing → omit default
                {"project": "Solomon EVT1", "HP": "N4", "HD": "N3"},
                {"project": "Thetis EVT0", "HP": "N4", "HD": "N4", "uHD": "N2"},
                {"project": "Thetis EVT1", "HP": "N4", "HD": "N4", "uHD": "N2"},
                {"project": "Ulysses EVT0", "HP": "N4", "HD": "N4", "uHD": "N2"},
                {"project": "Ulysses EVT1", "HP": "N4", "HD": "N4", "uHD": "N2"},
                {"project": "Vanguard EVT0", "HP": "N4", "HD": "N4", "uHD": "N2"},
                # Vanguard EVT1 missing entirely → fallback to lowest WNS
            ]
        }),
    },
]


# ---------------------------------------------------------------------------
# PDK version seed data
# ---------------------------------------------------------------------------

_SEED_PDK_VERSION = [
    # SF3 / Solomon
    {"PDK_ID": 881, "PROCESS": "SF3", "PROJECT": "S5E9955", "PROJECT_NAME": "Solomon", "MASK": "EVT1", "DK_GDS": "Solomon EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.0.0", "LVS": "V0.9.0.0", "PEX": "V0.9.0.0", "CREATED_AT": "2025-06-01 10:00:00", "CREATED_BY": "si0807.park"},
    # SF2 / Thetis
    {"PDK_ID": 882, "PROCESS": "SF2", "PROJECT": "S5E9965", "PROJECT_NAME": "Thetis", "MASK": "EVT0", "DK_GDS": "Thetis EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.2.0", "LVS": "V0.9.2.0", "PEX": "V0.9.2.0", "CREATED_AT": "2025-07-15 14:30:00", "CREATED_BY": "si0807.park"},
    {"PDK_ID": 883, "PROCESS": "SF2", "PROJECT": "S5E9965", "PROJECT_NAME": "Thetis", "MASK": "EVT1", "DK_GDS": "Thetis EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-09-20 09:15:00", "CREATED_BY": "si0807.park"},
    # SF2P / Ulysses
    {"PDK_ID": 900, "PROCESS": "SF2P", "PROJECT": "S5E9975", "PROJECT_NAME": "Ulysses", "MASK": "EVT0", "DK_GDS": "Thetis EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.2.0", "LVS": "V0.9.2.0", "PEX": "V0.9.2.0", "CREATED_AT": "2025-08-01 11:00:00", "CREATED_BY": "jh.kim"},
    {"PDK_ID": 901, "PROCESS": "SF2P", "PROJECT": "S5E9975", "PROJECT_NAME": "Ulysses", "MASK": "EVT0", "DK_GDS": "Ulysses EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-10-10 16:00:00", "CREATED_BY": "jh.kim"},
    {"PDK_ID": 910, "PROCESS": "SF2P", "PROJECT": "S5E9975", "PROJECT_NAME": "Ulysses", "MASK": "EVT1", "DK_GDS": "Ulysses EVT1", "IS_GOLDEN": 0, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2025-11-05 08:45:00", "CREATED_BY": "si0807.park"},
    {"PDK_ID": 912, "PROCESS": "SF2P", "PROJECT": "S5E9975", "PROJECT_NAME": "Ulysses", "MASK": "EVT1", "DK_GDS": "Ulysses EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V1.0.0.0", "LVS": "V1.0.0.0", "PEX": "V1.0.0.0", "CREATED_AT": "2025-12-25 09:00:00", "CREATED_BY": "si0807.park"},
    # SF2PP / Vanguard
    {"PDK_ID": 913, "PROCESS": "SF2PP", "PROJECT": "S5E9985", "PROJECT_NAME": "Vanguard", "MASK": "EVT0", "DK_GDS": "Ulysses EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.0.0", "LVS": "V0.9.0.0", "PEX": "V0.9.0.0", "CREATED_AT": "2026-01-12 13:20:00", "CREATED_BY": "si0807.park"},
    {"PDK_ID": 914, "PROCESS": "SF2PP", "PROJECT": "S5E9985", "PROJECT_NAME": "Vanguard", "MASK": "EVT0", "DK_GDS": "Vanguard EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.2.0", "LVS": "V0.9.0.0", "PEX": "V0.9.0.0", "CREATED_AT": "2026-02-01 10:00:00", "CREATED_BY": "si0807.park"},
    {"PDK_ID": 920, "PROCESS": "SF2PP", "PROJECT": "S5E9985", "PROJECT_NAME": "Vanguard", "MASK": "EVT1", "DK_GDS": "Vanguard EVT0", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V0.9.5.0", "LVS": "V0.9.5.0", "PEX": "V0.9.5.0", "CREATED_AT": "2026-01-20 09:00:00", "CREATED_BY": "jh.kim"},
    {"PDK_ID": 921, "PROCESS": "SF2PP", "PROJECT": "S5E9985", "PROJECT_NAME": "Vanguard", "MASK": "EVT1", "DK_GDS": "Vanguard EVT1", "IS_GOLDEN": 1, "VDD_NOMINAL": 0.72, "HSPICE": "V1.0.0.0", "LVS": "V1.0.0.0", "PEX": "V1.0.0.0", "CREATED_AT": "2026-01-23 09:00:00", "CREATED_BY": "si0807.park"},
]

# ---------------------------------------------------------------------------
# PPA data generation — full cross product with realistic values
# ---------------------------------------------------------------------------

# VDD ratios and types
_VDD_TYPES = ["UUD", "SUD", "UD", "NM", "OD", "SOD"]
_VDD_RATIOS = [0.75, 0.833, 0.903, 1.0, 1.111, 1.222]
_VDD_BASE = {"TT": 0.72, "SSPG": 0.76}

# CH → (CH_TYPE, available WNS levels)
_CH_WNS = {
    "CH138": ("uHD", ["N1", "N2"]),
    "CH168": ("HD", ["N1", "N2", "N3", "N4", "N5"]),
    "CH200": ("HP", ["N1", "N2", "N3", "N4", "N5"]),
}

# WNS → WNS_VAL (nm)
_WNS_VAL = {"N1": 12, "N2": 18, "N3": 25, "N4": 35, "N5": 48}

# Parameter space
_CORNERS = ["TT", "SSPG"]
_TEMPS = [-25, 25, 125]
_VTHS = ["ULVT", "SLVT", "VLVT", "LVT", "MVT", "RVT", "HVT"]
_DSS = ["D1", "D2", "D4"]
_CELLS = ["INV", "ND2", "NR2"]

# --- Scaling factors ---
# Base: INV D1, TT, 25°C, SLVT, N3, CH168, VDD=0.72
_BASE_FREQ = 4.82
_BASE_DPOWER = 0.0312
_BASE_ACCEFF = 11.52
_BASE_ACREFF = 1.85
_BASE_SPOWER = 0.00185
_BASE_IDDQ = 2.47
_VDD_NOM = 0.72

_CELL_FREQ = {"INV": 1.0, "ND2": 0.76, "NR2": 0.65}
_CELL_CAP = {"INV": 1.0, "ND2": 1.26, "NR2": 1.36}

_CORNER_FREQ = {"TT": 1.0, "SSPG": 0.85}
_CORNER_LEAK = {"TT": 1.0, "SSPG": 0.7}

_TEMP_FREQ = {-25: 1.02, 25: 1.0, 125: 0.94}
_TEMP_LEAK = {-25: 0.17, 25: 1.0, 125: 15.0}

_VTH_FREQ = {"ULVT": 1.08, "SLVT": 1.0, "VLVT": 0.93, "LVT": 0.86,
             "MVT": 0.78, "RVT": 0.70, "HVT": 0.62}
_VTH_LEAK = {"ULVT": 3.0, "SLVT": 1.0, "VLVT": 0.5, "LVT": 0.25,
             "MVT": 0.10, "RVT": 0.04, "HVT": 0.015}

_DS_FREQ = {"D1": 1.0, "D2": 1.0, "D4": 0.99}
_DS_POWER = {"D1": 1.0, "D2": 2.0, "D4": 4.0}

_WNS_FREQ = {"N1": 0.88, "N2": 0.94, "N3": 1.0, "N4": 1.06, "N5": 1.12}
_WNS_POWER = {"N1": 0.85, "N2": 0.92, "N3": 1.0, "N4": 1.08, "N5": 1.16}

_CH_FREQ = {"CH138": 0.92, "CH168": 1.0, "CH200": 1.06}
_CH_CAP = {"CH138": 0.88, "CH168": 1.0, "CH200": 1.12}


def _generate_ppa_data() -> list[dict]:
    """Generate full cross product PPA data for all PDK versions."""
    rows: list[dict] = []
    pdk_ids = [v["PDK_ID"] for v in _SEED_PDK_VERSION]

    for pdk_id in pdk_ids:
        rng = random.Random(pdk_id)
        pdk_freq_noise = rng.uniform(0.96, 1.04)
        pdk_leak_noise = rng.uniform(0.90, 1.10)

        for corner in _CORNERS:
            vdd_base = _VDD_BASE[corner]
            vdd_pairs = [
                (round(vdd_base * r, 3), vdd_type)
                for r, vdd_type in zip(_VDD_RATIOS, _VDD_TYPES)
            ]

            for vdd_num, vdd_type in vdd_pairs:
                vdd = vdd_num
                vdd_freq = (vdd / _VDD_NOM) ** 1.3
                vdd_power = (vdd / _VDD_NOM) ** 2
                vdd_leak = math.exp(3.5 * (vdd - _VDD_NOM))

                for temp in _TEMPS:
                    for vth in _VTHS:
                        for ds in _DSS:
                            for cell in _CELLS:
                                for ch, (ch_type, wns_levels) in _CH_WNS.items():
                                    for wns in wns_levels:
                                        noise = rng.uniform(0.98, 1.02)

                                        freq = (
                                            _BASE_FREQ
                                            * _CELL_FREQ[cell]
                                            * _CORNER_FREQ[corner]
                                            * _TEMP_FREQ[temp]
                                            * _VTH_FREQ[vth]
                                            * _DS_FREQ[ds]
                                            * vdd_freq
                                            * _WNS_FREQ[wns]
                                            * _CH_FREQ[ch]
                                            * pdk_freq_noise
                                            * noise
                                        )

                                        acceff = (
                                            _BASE_ACCEFF
                                            * _CELL_CAP[cell]
                                            * _DS_POWER[ds]
                                            * _CH_CAP[ch]
                                            * _WNS_POWER[wns]
                                        )

                                        d_energy = acceff * 1e-15 * vdd ** 2

                                        d_power = (
                                            _BASE_DPOWER
                                            * _CELL_FREQ[cell]
                                            * _DS_POWER[ds]
                                            * vdd_power
                                            * _WNS_POWER[wns]
                                            * _CH_CAP[ch]
                                            * (_CORNER_FREQ[corner] * _TEMP_FREQ[temp]
                                               * _VTH_FREQ[vth])
                                            * pdk_freq_noise
                                            * noise
                                        )

                                        acreff = _BASE_ACREFF / (
                                            _CELL_FREQ[cell]
                                            * _CORNER_FREQ[corner]
                                            * _TEMP_FREQ[temp]
                                            * _VTH_FREQ[vth]
                                            * vdd_freq
                                            * _WNS_FREQ[wns]
                                            * _CH_FREQ[ch]
                                        )

                                        s_power = (
                                            _BASE_SPOWER
                                            * _DS_POWER[ds]
                                            * _VTH_LEAK[vth]
                                            * _TEMP_LEAK[temp]
                                            * vdd_leak
                                            * _CORNER_LEAK[corner]
                                            * _WNS_POWER[wns]
                                            * _CH_CAP[ch]
                                            * pdk_leak_noise
                                            * noise
                                        )

                                        iddq = s_power / vdd * 1e3

                                        # Format VDD like real DB: strip leading zero
                                        vdd_str = f"{vdd:g}"
                                        if vdd_str.startswith("0."):
                                            vdd_str = vdd_str[1:]  # "0.54" → ".54"

                                        rows.append({
                                            "PDK_ID": pdk_id,
                                            "CELL": cell,
                                            "DS": ds,
                                            "CORNER": corner,
                                            "TEMP": str(temp),
                                            "VDD": vdd_str,
                                            "VDD_TYPE": vdd_type,
                                            "VTH": vth,
                                            "WNS": wns,
                                            "WNS_VAL": _WNS_VAL[wns],
                                            "CH": ch,
                                            "CH_TYPE": ch_type,
                                            "FREQ_GHZ": round(freq, 4),
                                            "D_POWER": round(d_power, 6),
                                            "D_ENERGY": round(d_energy, 18),
                                            "ACCEFF_FF": round(acceff, 2),
                                            "ACREFF_KOHM": round(acreff, 4),
                                            "S_POWER": round(s_power, 8),
                                            "IDDQ_NA": round(iddq, 4),
                                        })
    return rows
