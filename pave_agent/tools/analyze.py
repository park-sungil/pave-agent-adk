"""analyze tool: LLM-powered data analysis with code sandbox.

Generates Python analysis code via LLM, executes it in a sandbox,
and returns numerical results with optional charts.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import litellm

from pave_agent import settings
from pave_agent.sandbox import executor

logger = logging.getLogger(__name__)

# Load Analysis Skill content
_ANALYSIS_SKILL_PATH = settings.SKILLS_DIR / "analysis_skill" / "SKILL.md"
_ANALYSIS_SKILL: str = ""
if _ANALYSIS_SKILL_PATH.exists():
    _ANALYSIS_SKILL = _ANALYSIS_SKILL_PATH.read_text(encoding="utf-8")

_CODE_GEN_PROMPT = """당신은 반도체 PPA 데이터를 분석하는 Python 코드 생성기입니다.

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


def analyze(data: list[dict[str, Any]], analysis_request: str) -> dict[str, Any]:
    """데이터를 분석하고 수치 결과와 시각화를 생성한다.

    LLM이 분석용 Python 코드를 생성하고, 샌드박스에서 실행한다.

    Args:
        data: query_data로 조회한 PPA 데이터 (list of dicts).
        analysis_request: 사용자의 분석 요청 설명 (e.g., "VTH와 ION의 상관관계를 분석해줘").

    Returns:
        {"result": dict, "charts": list[str]} 형태의 분석 결과.
        코드 생성 실패 시 {"error": str} 반환.
    """
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
        response = litellm.completion(
            model=settings.LLM_MODEL,
            api_base=settings.LLM_API_BASE,
            api_key=settings.LLM_API_KEY or None,
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
