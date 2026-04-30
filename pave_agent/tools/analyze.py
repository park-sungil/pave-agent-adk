"""analyze tool: deterministic fast path + LLM fallback.

For known patterns (PDK benchmarking, simple stats, groupby), uses
deterministic Python functions — no LLM call, <100ms. Falls back to
LLM code generation + sandbox execution for ad-hoc requests, with
one retry on execution failure.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.tools import ToolContext

from pave_agent import llm, settings
from pave_agent.sandbox import executor
from pave_agent.tools import deterministic_analysis as det

logger = logging.getLogger(__name__)

_SKILL_PATH = settings.SKILL_DIR / "references" / "analysis.md"
_ANALYSIS_SKILL: str = _SKILL_PATH.read_text(encoding="utf-8") if _SKILL_PATH.exists() else ""

_CODE_GEN_PROMPT = """당신은 데이터를 분석하는 Python 코드 생성기입니다.

## 규칙
{analysis_skill}

## 입력 데이터
`data` 변수에 list of dicts로 제공됩니다 (총 {data_count}건).

컬럼: {columns}
PDK_ID별 행 수: {pdk_counts}
고유 값 (변하는 컬럼만):
{unique_values}

처음 2행 미리보기:
```json
{data_preview}
```

## 분석 요청
{analysis_request}

## 출력 요구사항
- 분석 결과를 `result` dict에 저장하세요.
- 시각화(matplotlib 차트)는 생성하지 마세요. `result`에 수치 결과만 담으세요.
- 코드만 출력하세요. 설명이나 마크다운 코드블록은 포함하지 마세요.
- import 문을 작성하지 마세요. pd, np, stats가 이미 있습니다.

## 집중 원칙
- 분석 요청에 명시된 metric만 계산하세요.
- 요청되지 않은 metric에 대한 계산은 포함하지 마세요.
"""

_REPAIR_PROMPT = """이전에 생성한 코드에서 에러가 발생했습니다.

## 에러
{error}

## 원래 코드
{original_code}

에러를 수정한 코드를 작성하세요. 코드만 출력하세요.
"""


# ---------------------------------------------------------------------------
# Pattern detection
# ---------------------------------------------------------------------------

def _detect_pattern(pdk_ids: list[int], analysis_request: str) -> str | None:
    """Detect known analysis pattern from inputs."""
    req = analysis_request.lower()

    # Two PDKs = benchmarking (dominant use case, 80%+)
    if len(pdk_ids) == 2:
        return "benchmark"

    if any(kw in req for kw in ("평균", "mean", "std", "통계", "stats", "min", "max")):
        return "stats"

    if any(kw in req for kw in ("그룹", "group", "별 평균", "별 통계")):
        return "groupby"

    return None


def _extract_metrics_from_request(analysis_request: str) -> list[str] | None:
    """Extract specific metric names if mentioned in the request."""
    req = analysis_request.upper()
    found = [m for m in det._METRIC_COLUMNS if m in req]
    return found if found else None


def _format_result(result: dict[str, Any], pattern: str | None = None) -> str:
    """Format analysis result as markdown text for the orchestrator to relay."""
    if "error" in result:
        return result["error"]

    if pattern == "benchmark" and "comparison" in result:
        return _format_benchmark(result)

    if pattern == "stats":
        return _format_stats(result)

    # Fallback: JSON
    return f"```json\n{json.dumps(result, indent=2, ensure_ascii=False, default=str)}\n```"


_AXIS_PRIORITY = ["VTH", "DS", "WNS", "CH", "CELL", "TEMP", "VDD", "CORNER"]


def _detect_varying_axis(comparison: list[dict[str, Any]]) -> str | None:
    """Pick the axis whose values vary across `comparison` rows.

    Prefers VTH (most-common benchmark axis), falling back through DS,
    WNS, CH, CELL, then PVT axes. Returns None if every axis is constant
    (single-row comparison).
    """
    if not comparison:
        return None
    for axis in _AXIS_PRIORITY:
        vals = {r.get(axis) for r in comparison if axis in r}
        if len(vals) > 1:
            return axis
    return None


def _format_benchmark(result: dict[str, Any]) -> str:
    """Format benchmark result as markdown — ratio-only, axis-as-columns.

    For each metric, builds a transposed table:
        |       | <axis-val-1> | <axis-val-2> | ... |
        | PDK A |       ...    |       ...    | ... |
        | PDK B |       ...    |       ...    | ... |
        | Ratio |     +x.x%    |     -y.y%    | ... |

    Single-row comparison (no axis varies) collapses to a 1-column table.
    Absolute delta is intentionally omitted — ratio (% change) is the
    only displayed comparison signal.
    """
    comparison = result.get("comparison", [])
    summary = result.get("summary", {})
    pdk_a = result.get("pdk_a", "A")
    pdk_b = result.get("pdk_b", "B")

    if not summary or not comparison:
        return "매칭된 데이터가 없습니다."

    axis = _detect_varying_axis(comparison)
    matched_count = result.get("matched_count", len(comparison))
    lines = [f"### PDK {pdk_a} vs {pdk_b} 비교 ({matched_count}건 매칭)\n"]

    if axis is not None:
        col_values = [str(r.get(axis)) for r in comparison]
    else:
        col_values = ["value"]

    for metric in summary.keys():
        lines.append(f"**{metric}** (axis: {axis or 'single'})")

        header = "| | " + " | ".join(col_values) + " |"
        sep = "| " + " | ".join("---" for _ in range(len(col_values) + 1)) + " |"
        lines.append(header)
        lines.append(sep)

        a_cells = [_fmt_value(r.get(f"{metric}_A")) for r in comparison]
        b_cells = [_fmt_value(r.get(f"{metric}_B")) for r in comparison]
        ratio_cells = [_fmt_pct(r.get(f"{metric}_pct")) for r in comparison]

        lines.append(f"| PDK A | {' | '.join(a_cells)} |")
        lines.append(f"| PDK B | {' | '.join(b_cells)} |")
        lines.append(f"| Ratio | {' | '.join(ratio_cells)} |")
        lines.append("")

    return "\n".join(lines).rstrip()


def _fmt_value(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, (int, float)):
        return f"{v:.4f}"
    return str(v)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "-"
    return f"{v:+.2f}%"


def _format_stats(result: dict[str, Any]) -> str:
    """Format simple stats as markdown table."""
    if not result:
        return "통계 데이터가 없습니다."

    lines = ["| Metric | Mean | Std | Min | Max | Count |"]
    lines.append("|--------|------|-----|-----|-----|-------|")

    for metric, stats in result.items():
        if not isinstance(stats, dict):
            continue
        lines.append(
            f"| {metric} | {stats.get('mean', '-'):.4f} | {stats.get('std', '-'):.4f} "
            f"| {stats.get('min', '-'):.4f} | {stats.get('max', '-'):.4f} "
            f"| {stats.get('count', '-')} |"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main tool function
# ---------------------------------------------------------------------------

def _load_data(tool_context: ToolContext, pdk_ids: list[int]) -> list[dict[str, Any]] | dict[str, Any]:
    """Load data from session state. Returns list of rows or error dict."""
    data: list[dict[str, Any]] = []
    for pdk_id in pdk_ids:
        filtered_key = f"_ppa_filtered_{pdk_id}"
        full_key = f"_ppa_data_{pdk_id}"
        rows = tool_context.state.get(filtered_key) or tool_context.state.get(full_key, [])
        if not rows:
            return {"error": f"PDK {pdk_id} 데이터가 세션에 없습니다. 먼저 query_ppa를 호출하세요."}
        source = "filtered" if tool_context.state.get(filtered_key) else "full"
        logger.info("[analyze] pdk_id=%s using %s data (%d rows)", pdk_id, source, len(rows))
        for row in rows:
            data.append({"PDK_ID": pdk_id, **row})

    if not data:
        return {"error": "분석할 데이터가 없습니다."}
    return data


def analyze(
    tool_context: ToolContext,
    pdk_ids: list[int],
    analysis_request: str,
    baseline_pdk_id: int | None = None,
) -> dict[str, Any]:
    """세션에 저장된 PPA 데이터를 분석하고 수치 결과를 반환한다.

    결정적 패턴 (benchmark, stats, groupby)은 LLM 없이 즉시 실행.
    그 외 ad-hoc 요청은 LLM 코드 생성 + sandbox 실행 (1회 retry).

    Args:
        tool_context: ADK tool context (session state).
        pdk_ids: 분석할 PDK ID 목록.
        analysis_request: 분석 요청 설명.
        baseline_pdk_id: 비교 시 베이스라인 PDK (예: "3nm 대비 2nm" → 3nm 의 pdk_id).
            지정 시 delta/pct 의 분모 = 베이스라인 PDK 값. 미지정이면 pdk_ids 의 첫 번째.

    Returns:
        {"formatted_result": str, "message": str}.
    """
    logger.info("[analyze] pdk_ids=%s, analysis_request=%s, baseline_pdk_id=%s",
                pdk_ids, analysis_request, baseline_pdk_id)

    if isinstance(pdk_ids, (int, float)):
        pdk_ids = [int(pdk_ids)]
    elif not isinstance(pdk_ids, list):
        return {"error": "pdk_ids must be a list of integers."}

    # Load data from session
    data = _load_data(tool_context, pdk_ids)
    if isinstance(data, dict) and "error" in data:
        return data

    # Detect pattern for fast path
    pattern = _detect_pattern(pdk_ids, analysis_request)
    logger.info("[analyze] detected pattern: %s", pattern)

    if pattern == "benchmark":
        metrics = _extract_metrics_from_request(analysis_request)
        result = det.benchmark_delta(data, pdk_ids, metrics, baseline_pdk_id=baseline_pdk_id)
        tool_context.state["_analysis_result"] = {"result": result}
        return {
            "formatted_result": _format_result(result, pattern),
            "message": "분석 완료 (deterministic).",
        }

    if pattern == "stats":
        columns = _extract_metrics_from_request(analysis_request)
        result = det.simple_stats(data, columns)
        tool_context.state["_analysis_result"] = {"result": result}
        return {
            "formatted_result": _format_result(result, pattern),
            "message": "분석 완료 (deterministic).",
        }

    if pattern == "groupby":
        # Extract group columns from request keywords
        group_cols = [c for c in ["VTH", "CORNER", "TEMP", "VDD", "DS", "WNS", "CH", "CELL"]
                      if c.lower() in analysis_request.lower()]
        agg_cols = _extract_metrics_from_request(analysis_request)
        result = det.groupby_agg(data, group_cols or ["VTH"], agg_cols)
        tool_context.state["_analysis_result"] = {"result": result}
        return {
            "formatted_result": _format_result(result),
            "message": "분석 완료 (deterministic).",
        }

    # -----------------------------------------------------------------------
    # LLM fallback path
    # -----------------------------------------------------------------------
    return _analyze_llm(tool_context, data, pdk_ids, analysis_request)


def _analyze_llm(
    tool_context: ToolContext,
    data: list[dict[str, Any]],
    pdk_ids: list[int],
    analysis_request: str,
) -> dict[str, Any]:
    """LLM code generation path with one retry on execution failure."""
    columns = list(data[0].keys())
    pdk_counts = {pid: sum(1 for r in data if r["PDK_ID"] == pid) for pid in pdk_ids}

    # Only include columns with >1 unique value (trimmed prompt)
    unique = {}
    for col in ("CELL", "CORNER", "TEMP", "VDD", "VDD_TYPE", "VTH", "DS", "WNS", "CH", "CH_TYPE"):
        vals = sorted({str(r[col]) for r in data if col in r})
        if len(vals) > 1:
            unique[col] = vals
    unique_str = "\n".join(f"  {k}: {v}" for k, v in unique.items()) or "  (모든 컬럼 단일 값)"

    preview = json.dumps(data[:2], ensure_ascii=False, default=str, indent=2)

    prompt = _CODE_GEN_PROMPT.format(
        analysis_skill=_ANALYSIS_SKILL,
        data_count=len(data),
        columns=columns,
        pdk_counts=pdk_counts,
        unique_values=unique_str,
        data_preview=preview,
        analysis_request=analysis_request,
    )

    # First attempt
    code = _generate_code(prompt)
    if code is None:
        return {"error": "코드 생성 실패."}

    exec_result = executor.execute(code, data)

    # Retry once on execution failure
    if "error" in exec_result:
        logger.warning("[analyze] first execution failed, retrying with repair prompt")
        repair_prompt = _REPAIR_PROMPT.format(error=exec_result["error"], original_code=code)
        code2 = _generate_code(repair_prompt)
        if code2 is None:
            return {"error": f"코드 수정 실패. 원래 에러:\n{exec_result['error']}"}

        exec_result = executor.execute(code2, data)
        if "error" in exec_result:
            return {"error": f"코드 실행 실패 (retry 후):\n{exec_result['error']}"}

    tool_context.state["_analysis_result"] = exec_result

    raw_result = exec_result.get("result", {})
    formatted = _format_result(raw_result)

    return {
        "formatted_result": formatted,
        "message": "분석 완료 (LLM).",
    }


def _generate_code(prompt: str) -> str | None:
    """Call LLM to generate analysis code. Returns code string or None."""
    try:
        code = llm.call_llm(
            settings.LLM_MODEL_ANALYZE,
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=4096,
        )
        # Strip markdown code fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        logger.info("Generated analysis code (%d chars):\n%s", len(code), code)
        return code
    except Exception as e:
        logger.error("LLM code generation failed: %s", e)
        return None
