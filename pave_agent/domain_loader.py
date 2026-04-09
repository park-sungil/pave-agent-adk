"""Selective domain-knowledge section loading from pave_domain.md.

Parses pave_domain.md into numbered sections and returns only the
sections relevant to the current interpret call, to avoid injecting
the entire 350+ line document on every LLM call.

Entry point: `select_sections(pdk_ids, rows, question)`.
"""

from __future__ import annotations

import re
from pathlib import Path

_DOMAIN_PATH = (
    Path(__file__).parent
    / "skills"
    / "pave-skill"
    / "references"
    / "pave_domain.md"
)

# Module-level cache of parsed sections
_SECTIONS: dict[str, str] | None = None

_COLS_TO_COUNT = (
    "CELL", "CORNER", "TEMP", "VDD", "VDD_TYPE",
    "VTH", "DS", "WNS", "CH", "CH_TYPE",
)


def _load_sections() -> dict[str, str]:
    """Parse pave_domain.md into sections keyed by the leading number."""
    global _SECTIONS
    if _SECTIONS is not None:
        return _SECTIONS

    _SECTIONS = {}
    if not _DOMAIN_PATH.exists():
        return _SECTIONS

    text = _DOMAIN_PATH.read_text(encoding="utf-8")
    parts = re.split(r"(?=^## \d+\.)", text, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^## (\d+)\.", part)
        if match:
            _SECTIONS[match.group(1)] = part
    return _SECTIONS


def _unique_counts(rows: list[dict]) -> dict[str, int]:
    """Count unique values per column in rows."""
    result: dict[str, int] = {}
    if not rows:
        return result
    for col in _COLS_TO_COUNT:
        vals = {str(r.get(col)) for r in rows if r.get(col) is not None}
        if vals:
            result[col] = len(vals)
    return result


def _keyword_match(q: str, keywords: tuple[str, ...]) -> bool:
    return any(kw in q for kw in keywords)


def select_sections(
    pdk_ids: list[int] | None,
    rows: list[dict] | None,
    question: str,
) -> str:
    """Pick relevant sections based on data shape + question keywords.

    Section 0 (column name mapping) is always included as a baseline so
    the LLM can cross-reference lowercase prose concepts with UPPERCASE
    DB columns.
    """
    sections = _load_sections()
    if not sections:
        return ""

    pdk_count = len(pdk_ids or [])
    rows = rows or []
    uniq = _unique_counts(rows)
    q = (question or "").lower()

    needed: set[str] = set()

    # ----------------- data-based triggers -----------------
    if pdk_count >= 2:
        needed.add("3")  # PPA trade-off
    if uniq.get("VTH", 0) >= 2:
        needed.add("5")  # design parameters (Vth subsection)
    if uniq.get("DS", 0) >= 2:
        needed.add("5")
    if uniq.get("CH", 0) >= 2:
        needed.add("5")
    if uniq.get("WNS", 0) >= 2:
        needed.add("5")
    if uniq.get("TEMP", 0) >= 2:
        needed.add("6")  # condition correlations
    if uniq.get("VDD", 0) >= 2:
        needed.add("6")
    if uniq.get("CORNER", 0) >= 2:
        needed.add("6")

    # ----------------- keyword-based triggers -----------------
    if _keyword_match(q, ("trade-off", "tradeoff", "trade off", "비교", " vs ", "대비")):
        needed.add("3")
    if _keyword_match(q, ("vth", "threshold", "flavor", "lvt", "hvt", "slvt", "mvt", "rvt", "vlvt", "ulvt")):
        needed.add("5")
    if _keyword_match(q, ("drive", "drive strength", " d1 ", " d2 ", " d4 ")):
        needed.add("5")
    if _keyword_match(q, ("cell height", "ch138", "ch168", "ch200", " hp ", " hd ", "uhd", "ch_type")):
        needed.add("5")
    if _keyword_match(q, ("nanosheet", "nanosheet_width", " n1 ", " n2 ", " n3 ", " n4 ", " n5 ")):
        needed.add("5")
    if _keyword_match(q, ("temp", "temperature", "온도", "-25", "125")):
        needed.add("6")
    if _keyword_match(q, ("vdd", "전압", "voltage")):
        needed.add("6")
    if _keyword_match(q, ("corner", "pvt", "sspg", " tt ")):
        needed.add("6")
    if _keyword_match(q, ("worst", "최악", "margin")):
        needed.add("6")  # 6.3 has worst-case mapping
    if _keyword_match(q, ("iddq", "leakage", "누설")):
        needed.add("7")
    if _keyword_match(q, ("cell type", " inv ", "nd2", "nr2", "nand", "nor")):
        needed.add("4")
    if _keyword_match(q, ("pdk", "버전", "version")):
        needed.add("2")

    # ----------------- fallback -----------------
    if not needed:
        if pdk_count >= 2:
            needed.add("3")  # trade-off for multi-PDK
        elif len(rows) <= 1:
            needed.add("1")  # parameter definitions for single-value interpretation
        else:
            needed.add("5")  # design parameter baseline

    # Always prepend section 0 (column mapping)
    # Limit total to 4 sections (0 + up to 3 others) to control prompt size
    chosen = sorted(s for s in needed if s != "0")
    if len(chosen) > 3:
        chosen = chosen[:3]

    result_parts: list[str] = []
    if "0" in sections:
        result_parts.append(sections["0"])
    for k in chosen:
        if k in sections:
            result_parts.append(sections[k])

    return "\n\n---\n\n".join(result_parts)
