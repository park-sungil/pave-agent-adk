"""analyze tool: LLM-powered data analysis with code sandbox.

Generates Python analysis code via LLM, executes it in a sandbox,
and returns numerical results with optional charts.
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
`data` 변수에 다음 데이터가 list of dicts로 제공됩니다:
```json
{data_preview}
```
(총 {data_count}건)

## 분석 요청
{analysis_request}

## 출력 요구사항
- 분석 결과를 `result` dict에 저장하세요.
- 시각화가 필요하면 `charts` list에 base64 PNG를 추가하세요.
- 코드만 출력하세요. 설명이나 마크다운 코드블록(```)은 포함하지 마세요.
- 필수 임포트는 이미 되어 있습니다 (pd, np, plt, stats, base64, BytesIO).
"""


def analyze(
    tool_context: ToolContext,
    pdk_ids: list[int],
    analysis_request: str,
) -> dict[str, Any]:
    """세션에 저장된 PPA 데이터를 분석하고 수치 결과와 시각화를 생성한다.

    query_data가 session state에 저장한 _ppa_data_{pdk_id} 데이터를 읽어
    LLM이 분석용 Python 코드를 생성하고, 샌드박스에서 실행한다.

    Args:
        tool_context: ADK tool context (session state에서 데이터 읽기).
        pdk_ids: 분석할 PDK ID 목록. session state의 _ppa_data_{id} 키로 데이터 조회.
        analysis_request: 사용자의 분석 요청 설명.

    Returns:
        {"result": dict, "charts": list[str]} 형태의 분석 결과.
        코드 생성 실패 시 {"error": str} 반환.
    """
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

    # Prepare data preview (first 5 rows)
    preview = json.dumps(data[:5], ensure_ascii=False, default=str, indent=2)

    prompt = _CODE_GEN_PROMPT.format(
        analysis_skill=_ANALYSIS_SKILL,
        data_preview=preview,
        data_count=len(data),
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

        logger.info("Generated analysis code (%d chars)", len(code))

    except Exception as e:
        logger.error("LLM code generation failed: %s", e)
        return {"error": f"코드 생성 실패: {e}"}

    # Execute in sandbox
    result = executor.execute(code, data)

    if "error" in result:
        logger.warning("Code execution failed, returning error")
        return {"error": f"코드 실행 실패:\n{result['error']}"}

    return result
