"""interpret tool: Domain-knowledge-based interpretation of PPA data.

Reads query_ppa/analyze results from session state (pdk_ids as reference),
loads only the relevant pave_domain.md sections via domain_loader, and
asks the LLM to interpret. Numbers are never passed through the LLM.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from google.adk.tools import ToolContext

from pave_agent import domain_loader, llm, settings
from pave_agent.rag import retriever

logger = logging.getLogger(__name__)

_RESPONSE_FORMAT_PATH = settings.SKILL_DIR / "references" / "interpretation.md"
_RESPONSE_FORMAT: str = (
    _RESPONSE_FORMAT_PATH.read_text(encoding="utf-8")
    if _RESPONSE_FORMAT_PATH.exists()
    else ""
)

_INTERPRET_PROMPT = """당신은 도메인 전문가입니다.
아래의 도메인 지식과 응답 포맷 규칙을 참고하여, 세션에 저장된 데이터를 해석하세요.

## 집중 원칙 (가장 중요)
- 사용자가 명시한 metric에만 집중하세요. (예: "주파수" 질문 → FREQ_GHZ만)
- 관련 없는 metric은 언급하지 마세요. (예: 주파수 질문인데 D_POWER/S_POWER 장황하게 설명 금지)
- 사용자가 "전체", "요약", "모든 metric" 등을 명시하거나 벤치마킹 비교인 경우에만 여러 metric을 다루세요.
- 사용자가 요청하지 않은 trade-off 분석, 설계 권장사항, 심층 해석을 추가하지 마세요. 질문에만 답하세요.
- **수치 계산 금지**: delta, %, 평균 등 어떤 산술도 당신이 직접 하지 마세요. 데이터에 있는 값만 그대로 사용하세요.

## 응답 포맷
{response_format}

## 도메인 지식 (질문에 관련된 섹션만 선택 주입됨)
{domain_sections}

## 참조 문서 (RAG 검색 결과)
{rag_context}

## 데이터
{data_summary}

## 사용자 질문
{question}

한국어로 답변하세요. 질문에 집중해서 간결하게 답하세요.
"""


def _collect_rows(
    tool_context: ToolContext, pdk_ids: list[int]
) -> list[dict[str, Any]]:
    """Read the latest filtered rows from session state for each PDK."""
    rows: list[dict[str, Any]] = []
    for pdk_id in pdk_ids:
        filtered_key = f"_ppa_filtered_{pdk_id}"
        full_key = f"_ppa_data_{pdk_id}"
        src = tool_context.state.get(filtered_key) or tool_context.state.get(full_key)
        if src:
            for row in src:
                rows.append({"PDK_ID": pdk_id, **row})
    return rows


def interpret(
    tool_context: ToolContext,
    pdk_ids: list[int],
    question: str,
) -> str:
    """세션에 저장된 PPA 데이터를 도메인 맥락에서 해석한다.

    세션 state (`_ppa_filtered_{pdk_id}` 또는 `_analysis_result`)에서 직접
    데이터를 읽기 때문에 LLM이 숫자를 전달하거나 재작성하지 않는다.

    Args:
        tool_context: ADK tool context (session state).
        pdk_ids: 해석 대상 PDK ID 목록. query_ppa 호출 시 사용한 것과 동일.
        question: 사용자의 질문.

    Returns:
        도메인 해석 텍스트.
    """
    logger.info("[interpret] pdk_ids=%s, question=%s", pdk_ids, question)

    if isinstance(pdk_ids, (int, float)):
        pdk_ids = [int(pdk_ids)]
    elif not isinstance(pdk_ids, list):
        return "pdk_ids must be a list of integers."

    # Prefer analyze result if available (analyze stores numeric result in _analysis_result)
    analysis_result = tool_context.state.get("_analysis_result")
    rows = _collect_rows(tool_context, pdk_ids)

    if analysis_result:
        data_summary = json.dumps(
            analysis_result.get("result", analysis_result),
            ensure_ascii=False,
            default=str,
            indent=2,
        )
    elif rows:
        preview = rows[:20]
        data_summary = json.dumps(preview, ensure_ascii=False, default=str, indent=2)
        if len(rows) > 20:
            data_summary += f"\n... (총 {len(rows)}건 중 상위 20건)"
    else:
        data_summary = "(세션에 데이터 없음)"

    # Select domain sections based on data + question
    domain_sections = domain_loader.select_sections(pdk_ids, rows, question)
    logger.info("[interpret] domain_sections len=%d chars", len(domain_sections))

    # RAG retrieval
    rag_context = retriever.retrieve(question, top_k=5)

    prompt = _INTERPRET_PROMPT.format(
        response_format=_RESPONSE_FORMAT,
        domain_sections=domain_sections,
        rag_context=rag_context,
        data_summary=data_summary,
        question=question,
    )

    try:
        return llm.call_llm(
            settings.LLM_MODEL_INTERPRET,
            [{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
    except Exception as e:
        logger.error("Interpret LLM call failed: %s", e)
        return f"해석 생성 중 오류가 발생했습니다: {e}"
