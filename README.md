# pave-agent

반도체 PDK Cell-level PPA (Power, Performance, Area) 분석을 위한 챗봇 에이전트.

Google ADK (Agent Development Kit) 기반으로 구현되었으며, 자연어 질문에 대해 DB 조회, 분석, 시각화, 도메인 해석을 수행한다.

## Setup

```bash
uv sync          # 또는 pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your configuration
```

## Run

```bash
# 웹 UI (프로젝트 루트에서 실행)
uv run adk web .

# CLI 모드
uv run adk run pave_agent
```

> `adk web`은 인자로 **에이전트 디렉토리의 부모 경로**를 받는다.
> 프로젝트 루트에서 `.`을 넘기면 하위의 `pave_agent/` 폴더를 자동 탐색한다.

## Architecture

```
[사용자] ↔ [오케스트레이터 (root Agent)]
              │
        ┌─────┼──────────┬──────────┐
   [query_data]    [analyze]    [interpret]
    순수 코드     LLM+sandbox    LLM+RAG
```

- **query_data**: SQL 템플릿 기반 Oracle DB 조회. sql_skill의 Cache 설정에 따라 소량 테이블은 최초 1회 전체 조회 후 캐싱
- **analyze**: LLM이 생성한 Python 코드를 샌드박스에서 실행하여 수치 분석/시각화
- **interpret**: Domain Skill(정적 규칙) + RAG(동적 문서) 기반 도메인 맥락 해석

## Test

```bash
pytest
```
