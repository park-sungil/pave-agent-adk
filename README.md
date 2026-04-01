# pave-agent

반도체 PDK Cell-level PPA (Power, Performance, Area) 분석을 위한 챗봇 에이전트.

Google ADK (Agent Development Kit) 기반으로 구현되었으며, 자연어 질문에 대해 DB 조회, 분석, 시각화, 도메인 해석을 수행한다.

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your configuration
```

## Run

```bash
adk web pave_agent
# or
adk run pave_agent
```

## Architecture

```
[사용자] ↔ [오케스트레이터 (root Agent)]
              │
        ┌─────┼──────────┬──────────┐
   [query_data]    [analyze]    [interpret]
    순수 코드     LLM+sandbox    LLM+RAG
```

- **query_data**: SQL 템플릿 기반 Oracle DB 조회
- **analyze**: LLM이 생성한 Python 코드를 샌드박스에서 실행하여 수치 분석/시각화
- **interpret**: Domain Skill(정적 규칙) + RAG(동적 문서) 기반 도메인 맥락 해석

## Test

```bash
pytest
```
