"""analyze tool: LLM-powered data analysis with code sandbox.

Reads PPA data from session state, generates Python analysis code via LLM,
executes it in a sandbox, and stores results back in session state.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm
from google.adk.tools import ToolContext

from pave_agent import settings
from pave_agent.sandbox import executor

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
고유 값:
{unique_values}

처음 3행 미리보기:
```json
{data_preview}
```

## 분석 요청
{analysis_request}

## 출력 요구사항
- 분석 결과를 `result` dict에 저장하세요.
- 시각화가 필요하면 `charts` list에 base64 PNG를 추가하세요.
- 코드만 출력하세요. 설명이나 마크다운 코드블록은 포함하지 마세요.
- import 문을 작성하지 마세요. pd, np, plt, stats, base64, BytesIO가 이미 있습니다.
"""


def analyze(
    tool_context: ToolContext,
    pdk_ids: list[int],
    analysis_request: str,
) -> dict[str, Any]:
    """세션에 저장된 PPA 데이터를 분석하고 수치 결과와 시각화를 생성한다.

    Args:
        tool_context: ADK tool context (session state).
        pdk_ids: 분석할 PDK ID 목록.
        analysis_request: 분석 요청 설명.

    Returns:
        {"result": dict, "charts_count": int, "message": str}.
        결과는 session state에 _analysis_result로 저장됨.
    """
    logger.info("[analyze] pdk_ids=%s, analysis_request=%s", pdk_ids, analysis_request)

    if isinstance(pdk_ids, (int, float)):
        pdk_ids = [int(pdk_ids)]
    elif not isinstance(pdk_ids, list):
        return {"error": "pdk_ids must be a list of integers."}

    data: list[dict[str, Any]] = []
    for pdk_id in pdk_ids:
        key = f"_ppa_data_{pdk_id}"
        rows = tool_context.state.get(key, [])
        if not rows:
            return {"error": f"PDK {pdk_id} 데이터가 세션에 없습니다. 먼저 query_data를 호출하세요."}
        for row in rows:
            data.append({"PDK_ID": pdk_id, **row})

    if not data:
        return {"error": "분석할 데이터가 없습니다."}

    # Build context for LLM
    columns = list(data[0].keys())
    pdk_counts = {pid: sum(1 for r in data if r["PDK_ID"] == pid) for pid in pdk_ids}

    unique = {}
    for col in ("CELL", "CORNER", "TEMP", "VDD", "VDD_TYPE", "VTH", "DS", "WNS", "CH", "CH_TYPE"):
        vals = sorted({str(r[col]) for r in data if col in r})
        if vals:
            unique[col] = vals
    unique_str = "\n".join(f"  {k}: {v}" for k, v in unique.items())

    preview = json.dumps(data[:3], ensure_ascii=False, default=str, indent=2)

    prompt = _CODE_GEN_PROMPT.format(
        analysis_skill=_ANALYSIS_SKILL,
        data_count=len(data),
        columns=columns,
        pdk_counts=pdk_counts,
        unique_values=unique_str,
        data_preview=preview,
        analysis_request=analysis_request,
    )

    try:
        llm_kwargs: dict = {"model": settings.LLM_MODEL}
        if settings.LLM_API_BASE:
            llm_kwargs["api_base"] = settings.LLM_API_BASE
        if settings.LLM_API_KEY:
            llm_kwargs["api_key"] = settings.LLM_API_KEY
        response = litellm.completion(
            **llm_kwargs,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=4096,
        )
        code = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if code.startswith("```"):
            lines = code.split("\n")
            code = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        logger.info("Generated analysis code (%d chars):\n%s", len(code), code)

    except Exception as e:
        logger.error("LLM code generation failed: %s", e)
        return {"error": f"코드 생성 실패: {e}"}

    # Execute in sandbox
    exec_result = executor.execute(code, data)

    if "error" in exec_result:
        logger.warning("Code execution failed")
        return {"error": f"코드 실행 실패:\n{exec_result['error']}"}

    # Store full result in session (including charts)
    tool_context.state["_analysis_result"] = exec_result

    # Return summary to LLM (without charts — they're too large for context)
    return {
        "result": exec_result.get("result", {}),
        "charts_count": len(exec_result.get("charts", [])),
        "message": f"분석 완료. 차트 {len(exec_result.get('charts', []))}개 생성됨. 세션에 저장됨.",
    }
