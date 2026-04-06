"""interpret tool: Domain-knowledge-based interpretation of data/analysis results.

Combines static Domain Skill rules with dynamic RAG retrieval
to provide domain-specific interpretation.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import litellm

from pave_agent import settings
from pave_agent.rag import retriever

logger = logging.getLogger(__name__)

_SKILL_PATH = settings.SKILL_DIR / "references" / "interpretation.md"
_DOMAIN_SKILL: str = _SKILL_PATH.read_text(encoding="utf-8") if _SKILL_PATH.exists() else ""

_INTERPRET_PROMPT = """당신은 도메인 전문가입니다.
아래의 도메인 규칙과 참조 문서를 바탕으로, 주어진 데이터/분석 결과를 해석하세요.

## 도메인 규칙 (항상 적용)
{domain_skill}

## 참조 문서 (RAG 검색 결과)
{rag_context}

## 데이터/분석 결과
{data_summary}

## 사용자 질문/맥락
{question}

한국어로 답변하세요.
"""


def interpret(
    data: dict[str, Any] | list[dict[str, Any]],
    question: str,
    context: str = "",
) -> str:
    """데이터/분석 결과를 도메인 맥락에서 해석한다.

    Domain Skill(정적 규칙)과 RAG(동적 문서 검색)를 결합하여 해석을 생성한다.

    Args:
        data: 조회 결과 또는 분석 결과.
        question: 사용자의 질문 또는 해석 맥락.
        context: 추가 맥락 정보 (선택).

    Returns:
        도메인 해석 텍스트.
    """
    logger.info("[interpret] question=%s, data_type=%s, context=%s", question, type(data).__name__, context)

    # Prepare data summary
    if isinstance(data, list):
        data_summary = json.dumps(data[:20], ensure_ascii=False, default=str, indent=2)
        if len(data) > 20:
            data_summary += f"\n... (총 {len(data)}건 중 상위 20건)"
    else:
        data_summary = json.dumps(data, ensure_ascii=False, default=str, indent=2)

    # RAG retrieval: search for relevant domain documents
    rag_query = f"{question} {context}".strip()
    rag_context = retriever.retrieve(rag_query, top_k=5)

    prompt = _INTERPRET_PROMPT.format(
        domain_skill=_DOMAIN_SKILL,
        rag_context=rag_context,
        data_summary=data_summary,
        question=question,
    )

    try:
        llm_kwargs: dict = {"model": settings.LLM_MODEL_INTERPRET}
        if settings.LLM_API_BASE:
            llm_kwargs["api_base"] = settings.LLM_API_BASE
        if settings.LLM_API_KEY:
            llm_kwargs["api_key"] = settings.LLM_API_KEY
        response = litellm.completion(
            **llm_kwargs,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=4096,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error("Interpret LLM call failed: %s", e)
        return f"해석 생성 중 오류가 발생했습니다: {e}"
