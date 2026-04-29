"""Unit tests for domain_loader.select_sections behavior."""

import re

from pave_agent.domain_loader import select_sections


def test_section_0_always_present():
    """Section 0 (column mapping) is the baseline — always included."""
    result = select_sections([], [], "")
    assert result.startswith("## 0.") or "\n## 0." in result, result[:200]


def test_section_0_present_with_keywords():
    """Section 0 still included even when other sections are triggered by keywords."""
    result = select_sections([1, 2], [], "trade-off vth temperature iddq")
    assert "## 0." in result


def test_max_4_sections():
    """Even with all keywords + many unique cols, output is capped at 4 sections (0 + 3 others)."""
    rows = [
        {"VTH": v, "DS": d, "CH": c, "TEMP": t, "VDD": vd, "CORNER": cn}
        for v in ("LVT", "HVT", "SVT")
        for d in ("D1", "D2")
        for c in ("CH138", "CH200")
        for t in ("-25", "25", "125")
        for vd in (".54", ".72")
        for cn in ("TT", "SSPG")
    ]
    result = select_sections(
        [1, 2, 3],
        rows,
        "trade-off vth drive cell height nanosheet temp vdd corner iddq",
    )
    headings = re.findall(r"^## \d+\.", result, flags=re.MULTILINE)
    assert len(headings) <= 4, f"got {len(headings)} sections: {headings}"
