# CLAUDE.md

## 프로젝트 개요

pave-agent는 반도체 PDK Cell-level PPA (Power, Performance, Area) 분석을 위한 챗봇 에이전트다. 사용자가 자연어로 질문하면, DB에서 데이터를 조회하고 분석·시각화·해석하여 의사결정을 지원한다.

## 프레임워크

Google ADK (Agent Development Kit)를 사용한다.

- ADK의 root Agent + tools 모델이 pave-agent의 "오케스트레이터 + tool 호출" 구조와 일치한다.
- 도메인 확장 시 sub-agent를 붙이는 계층적 구조가 자연스럽다.
- LLM 연결은 LiteLLM을 통해 다양한 provider를 지원한다. `api_base`가 설정되면 OpenAI-compatible 엔드포인트, 비어있으면 provider 네이티브 API를 사용한다.

## 실행

```bash
uv run adk web .              # 웹 UI (프로젝트 루트에서 실행)
uv run adk run pave_agent     # CLI 모드
```

`adk web`은 인자로 에이전트 디렉토리의 **부모 경로**를 받는다. 프로젝트 루트에서 `.`을 넘기면 하위의 `pave_agent/` 폴더를 자동 탐색한다.

## 아키텍처

```
[사용자] ↔ [오케스트레이터 LLM (root Agent)]
              │ 대화 관리 + 의도 파악 + tool 호출 결정
              │ 프롬프트에 의도별 처리 가이드 포함
              │
        ┌─────┼──────────┬──────────┐
   [query_data]    [analyze]    [interpret]
    순수 코드     LLM+sandbox    LLM
        │             │            │
   SQL Skill     Analysis Skill  Domain Skill ← 핵심 규칙 (항상 주입)
        │             │            │
   [Oracle DB]  [code sandbox] [RAG retriever] ← 사내 RAG API
```

## 파일 구조

```
pave_agent/
├── agent.py                  # ADK 진입점. root_agent 정의 + _init_state callback
├── prompts.py                # 오케스트레이터 INSTRUCTION (대화 관리, tool 선택, 응답 규칙)
├── settings.py               # 환경변수 로딩 (LLM, DB)
├── llm.py                    # LiteLLM 어댑터. key/header 모드 분기, ADK OTel span 보존
├── domain_loader.py          # pave_domain.md 섹션 선택 로딩 (interpret 프롬프트 트리밍)
├── tools/
│   ├── query_data.py         #   query_versions, query_ppa (순수 코드, LLM 없음)
│   ├── analyze.py            #   결정적 fast path (benchmark/stats/groupby) + LLM fallback
│   ├── deterministic_analysis.py  # benchmark_delta, simple_stats, groupby_agg
│   └── interpret.py          #   도메인 해석 (LLM + 선택된 pave_domain 섹션 + RAG)
├── skills/
│   └── pave-skill/
│       ├── SKILL.md
│       └── references/
│           ├── sql.md            # SQL 템플릿/스키마 (참고용)
│           ├── analysis.md       # 분석 코드 생성 컨벤션 (analyze 프롬프트에 주입)
│           ├── interpretation.md # 응답 포맷 규칙 (interpret 프롬프트에 주입)
│           └── pave_domain.md    # 도메인 지식 (domain_loader가 섹션 선택)
├── db/
│   ├── oracle_client.py      # Oracle 클라이언트. ORACLE_PASSWORD 비면 mock_db로 fallthrough
│   └── mock_db.py            # SQLite mock DB (개발/테스트용)
├── rag/
│   └── retriever.py          # 사내 RAG API 호출 (TODO: 엔드포인트 연결)
└── sandbox/
    └── executor.py           # LLM 생성 코드 샌드박스 실행 (analyze fallback path만)

tests/
├── conftest.py               # FakeToolContext, ppa_loaded_state, mock_db 리셋
├── unit/                     # 순수 함수: select_sections, deterministic_analysis
├── tool/                     # 도구 단위: query_ppa, query_versions, analyze fast paths
├── agent/                    # Phase 2 — adk eval framework (EvalSet JSON)
│   └── eval_sets/            # ch_type_clarification, simple_freq_query, direct_data_access, node_benchmarking, ambiguous_pvt
├── test_analyze.py           # 샌드박스 executor
└── test_interpret.py         # RAG fallback

docs/                          # 사용자 + 사내 Claude Code 인계용
├── edd-methodology.md         # EDD 철학 + 의사결정 log + mocking 규칙
└── phase2-3-roadmap.md        # 사내 환경 다음 단계
```

## LLM 호출 포인트

LLM 호출은 정확히 3곳이다. 각각 역할이 분리되어 있으며, 프롬프트가 단일 역할에 집중한다.

- **오케스트레이터**: 대화 관리, 의도 파악, tool 호출 결정. 프롬프트에는 대화 관리 규칙과 tool 선택 가이드만 포함한다.
- **analyze**: 분석용 Python 코드 생성. 프롬프트에는 코드 생성 규칙과 Analysis Skill만 포함한다.
- **interpret**: 도메인 지식 기반 결과 해석. 프롬프트에는 해석 규칙, Domain Skill, RAG 검색 결과를 포함한다.

## 컴포넌트

### 오케스트레이터 (root Agent)

- 사용자와의 멀티턴 대화를 관리한다.
- 사용자 의도를 파악하고 어떤 tool을 어떤 순서로 호출할지 결정한다.
- 의도별 처리 방식은 프롬프트에 가이드로 포함한다. 별도 코드 라우팅 레이어 없음.
- 예: 단순 조회 → query_data → interpret, 상관분석 → query_data → analyze → interpret

### query_data (tools, 순수 코드)

현재 두 개의 explicit tool로 분리되어 있다:
- **query_versions**(project, project_name, process, mask, node): PDK 버전 조회. `node="2nm"`/`"3nm"`는 코드에서 SF2/SF2P/SF2PP, SF3로 확장된다. 응답 `data` 는 사용자 표시용 (PDK_ID/CREATED_AT/CREATED_BY 자동 제외). `pdk_id_by_idx` (IDX→pdk_id) 와 `auto_selected_pdk_id` (결과 1개일 때) 를 별도 필드로 제공해서 orchestrator 가 query_ppa 호출 시 사용.
- **query_ppa**(pdk_id, cell, corner, temp, vdd, vdd_type, vth, ds, wns, ch, ch_type): PPA 데이터 조회. `pdk_id` 필수.

둘 다 LLM 호출 없음, 순수 코드. SQL은 하드코딩(템플릿 파싱 아님). 세션 시작 시 PDK 버전 + default WNS config를 미리 로드해서 캐싱한다.

#### 세션 캐시 키

- `_cache_ANTSDB.PAVE_PDK_VERSION_VIEW`: 전체 PDK 버전 (1회 로드)
- `_cache_AT9.PDKPAS_CONFIG_JSON_FAV`: default WNS config
- `_ppa_data_{pdk_id}`: PDK별 전체 PPA rows (첫 query_ppa 시 로드)
- `_ppa_deps_{pdk_id}`: PDK별 의존성 (ch/corner/cell/temp/vth + default_wns)
- `_ppa_filtered_{pdk_id}`: 직전 query_ppa의 필터+집계 결과 (analyze가 재사용)

#### Default 적용 규칙 (query_ppa)

사용자가 명시하지 않은 파라미터는 query_ppa가 자동으로 default를 적용한다:

| 파라미터 | Default | 비고 |
|---------|---------|------|
| corner | `TT` | per-axis default. 사용자 명시 (예: SSPG) 면 그대로 유지, 누락 axes 만 채움. |
| temp | `25` | per-axis default. 사용자 명시값 유지. |
| vdd_type | `NM` (단, 사용자가 raw vdd 주면 스킵) | per-axis default. 표준 PVT 대안 안내는 프롬프트에서 자연어로. |
| cell | `AVG(INV, ND2, NR2)` | 평균 집계. CELL 라벨은 `"AVG(INV,ND2,NR2)"` |
| ds | `AVG(D1, D4)` | 평균 집계 |
| wns | `(project_name, mask, ch_type)` 별 config | `AT9.PDKPAS_CONFIG_JSON_FAV`에서 로드. config 없으면 최소 WNS로 fallback |
| ch_type | **필수** | 없으면 `needs_input` 반환 → orchestrator가 사용자에게 HP/HD/uHD 질문 |
| vth | 전체 반환 | default 없음 |

사용자가 명시한 값은 절대 교정하지 않는다. 사용자가 `vdd`(숫자)를 명시하면 `vdd_type` default는 스킵한다 (중복 필터 방지). PVT 표준 대안 (T1/T2/T3) 안내는 프롬프트에서 자연어로 처리 (코드는 단순 per-axis default 만).

#### query_ppa 응답 구조

```
{
  "count": N,
  "pdk_ids": [pdk_id],
  "pdk_info": {PROCESS, PROJECT_NAME, MASK, DK_GDS, HSPICE, LVS, PEX, ...},
  "dependencies": {ch, corner, cell, temp, vth, ...},
  "applied_defaults": {...},
  "data": [...],   # 결과가 50행 이하일 때만 포함
  "message": "..."
}
```

orchestrator는 `applied_defaults`를 보고 사용자에게 어떤 default가 적용됐는지 알리고 대안 옵션(T1/T2/T3, 특정 cell, 특정 ds 등)을 제시해야 한다. 50행 초과 시 `data`는 생략되고 analyze가 `_ppa_filtered_{pdk_id}` 캐시에서 읽어 처리한다.

### analyze (tool, deterministic fast path + LLM fallback)

- 패턴 감지로 라우팅: 2-PDK 비교 → benchmark, "평균/stats" 키워드 → simple_stats, "그룹/별" → groupby_agg.
- 결정적 패턴은 `deterministic_analysis.py`의 pandas 함수로 즉시 처리 (LLM 없음, <100ms). 80% 이상의 use case 가 여기 해당.
- 패턴 미매칭 시 LLM이 분석 코드를 생성하고 샌드박스에서 실행. 1회 retry (실패 시 에러 + 원래 코드를 repair prompt 로 재요청).
- 응답은 `formatted_result` (markdown text). 숫자 raw dict 가 LLM 으로 흘러가지 않도록 미리 포맷.
- 시각화는 현재 비활성 (`6afadb5` 롤백). 추후 demo 후 복귀 예정.

### interpret (tool, LLM)

- 데이터 조회 결과 또는 분석 결과를 받아 도메인 맥락에서 해석한다.
- 입력은 세션 state 에서 직접 읽음 (`_ppa_filtered_{pdk_id}`, `_analysis_result`) — pdk_ids 만 인자로 받음.
- 두 가지 지식 소스를 결합:
  - **pave_domain.md (정적 지식)**: `domain_loader.select_sections(pdk_ids, rows, question)` 가 데이터 shape + 질문 키워드로 관련 섹션만 골라 주입 (Section 0 always + 최대 3개). 전체 350+ 줄 다 넣지 않음.
  - **RAG retriever (동적 지식)**: 사내 RAG API. (TODO: 엔드포인트 연결)
- analyze와 분리한 이유: analyze는 계산(범용), interpret는 해석(도메인 특화). 도메인 확장 시 analyzer는 재사용하고 interpret의 도메인 문서만 교체한다.

## DB 구성

- **Oracle DB**: PPA 데이터, PDK 버전 정보. query_data가 SQL로 조회.
- **SQLite mock DB** (개발용): 실제 스키마(PAVE_PDK_VERSION_VIEW, PAVE_PPA_DATA_VIEW) 기반. ORACLE_PASSWORD 미설정 시 자동 사용.
- **RAG**: 사내 시스템에서 인덱스 생성/벡터 DB 관리. 이 프로젝트에서는 retriever로 데이터를 가져오기만 한다.

## 도메인 지식 주입

### 정적 지식: pave-skill/references/

단일 skill (`pave-skill`) 안에 여러 reference 문서가 있다:

- **sql.md**: 뷰 스키마, SQL 템플릿. 현재 query_data.py 가 SQL 을 하드코딩 — sql.md 는 참고용.
- **analysis.md**: 분석 코드 생성 컨벤션, 전처리 규칙 → analyze 프롬프트에 주입.
- **interpretation.md**: 응답 포맷 규칙 → interpret 프롬프트에 주입.
- **pave_domain.md**: 핵심 도메인 지식 (350+ 줄, Section 0~7) → `domain_loader` 가 선택해서 interpret 프롬프트에 주입.

### 동적 지식: RAG

사내 RAG 시스템이 인덱스 생성, 벡터 DB 저장, 검색을 담당한다. pave-agent는 retriever를 통해 API를 호출하여 관련 문서 조각을 가져온다. (TODO: 엔드포인트 연결)

## 테스트

3-layer pyramid (`tests/unit/` → `tests/tool/` → `tests/agent/`). 기본 28개 deterministic 테스트가 ~7s 에 오프라인 실행. Phase 2 agent eval 은 `PAVE_REAL_LLM=1` 로 gated.

```bash
uv run --extra dev pytest -q                          # 기본
PAVE_REAL_LLM=1 uv run --extra dev pytest tests/agent # real LLM 실행
```

자세한 레이어 책임, EvalSet 작성법, mocking 규칙, 트러블슈팅은 [`tests/README.md`](tests/README.md) 참조. Phase 2/3 전체 계획은 `/Users/sungil/.claude/plans/cuddly-hugging-wadler.md`.

## 확장

새로운 도메인 추가 시:
1. `skills/<new-skill>/references/` 에 도메인 문서 작성 (sql.md / analysis.md / interpretation.md / domain.md)
2. `prompts.py` 의 INSTRUCTION 재작성 (대화 흐름, tool 선택 가이드)
3. `tools/query_data.py` 의 SQL/스키마 로직은 도메인마다 다름 — 새 도메인이면 별도 모듈로 분리
4. `domain_loader.py` 는 domain.md 가 표준 섹션 헤딩 규칙을 따르면 재사용 가능

### 엔진과 도메인 문서의 분리

| 도구 | 엔진 (코드) | 도메인 문서 (지식) |
|------|-------------|-------------|
| query_data | DB 호출, 필터링, 집계, 캐시 | sql.md (스키마 참고용), 도메인별 default 규칙은 코드에 인라인 |
| analyze | 패턴 라우팅, fast-path, LLM 코드 생성, 샌드박스 | analysis.md (코드 컨벤션) |
| interpret | LLM 호출, RAG 연결, 도메인 섹션 선택 | interpretation.md + pave_domain.md |

## 도메인 용어

- **PPA**: Power, Performance, Area
- **PDK**: Process Design Kit
- **RO**: Ring Oscillator
- **SSPG corner**: 공정 코너 조건
- **LVT/HVT/SVT**: Low/High/Standard Voltage Threshold
- **BSIM-CMG**: 트랜지스터 모델 표준
- **Liberty 파일**: 셀 타이밍/파워 정보 파일
- **DK**: Design Kit
- **TR**: Transistor
- **HSPICE**: 회로 시뮬레이터
- **FDRY**: Foundry