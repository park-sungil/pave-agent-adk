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
├── agent.py                  # ADK 진입점. 오케스트레이터 에이전트 + instruction
├── settings.py               # 환경변수 로딩 (LLM, DB 설정)
├── tools/                    # 범용 도구 엔진 (skill이 주입하는 지식으로 동작)
│   ├── query_data.py         #   sql_skill에서 SQL 템플릿/캐시 설정 파싱 → DB 조회
│   ├── analyze.py            #   analysis_skill → LLM 코드 생성 → 샌드박스 실행
│   └── interpret.py          #   domain_skill → LLM 해석 + RAG 컨텍스트
├── skills/                   # 도메인 지식 (pave 전용, 교체 가능)
│   ├── sql_skill/SKILL.md    #   DB 스키마, SQL 템플릿, 캐시 설정, 엔티티 매핑
│   ├── analysis_skill/SKILL.md  # 분석 코드 생성 패턴, 차트 규칙
│   └── domain_skill/SKILL.md #   파라미터 해석 규칙, 코너 의미, PPA 트레이드오프
├── cache/
│   └── data_cache.py         # 모듈 레벨 dict 캐시
├── db/
│   ├── oracle_client.py      # DB 클라이언트. execute_query()만 제공
│   └── mock_db.py            # SQLite mock DB (개발용)
├── rag/
│   └── retriever.py          # 사내 RAG API 호출 (TODO: 엔드포인트 연결)
└── sandbox/
    └── executor.py           # LLM 생성 코드 샌드박스 실행
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
- **query_versions**(project, project_name, process, mask, node): PDK 버전 조회. `node="2nm"`/`"3nm"`는 코드에서 SF2/SF2P/SF2PP, SF3로 확장된다.
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
| corner/temp/vdd_type | `TT/25/NM` (T1) | 표준 triple 매칭. 모호(예: SSPG만) → 되묻기. 다른 표준: T2 `SSPG/125/SOD`, T3 `SSPG/-25/SUD` |
| cell | `AVG(INV, ND2, NR2)` | 평균 집계. CELL 라벨은 `"AVG(INV,ND2,NR2)"` |
| ds | `AVG(D1, D4)` | 평균 집계 |
| wns | `(project_name, mask, ch_type)` 별 config | `AT9.PDKPAS_CONFIG_JSON_FAV`에서 로드. config 없으면 최소 WNS로 fallback |
| ch_type | **필수** | 없으면 `needs_input` 반환 → orchestrator가 사용자에게 HP/HD/uHD 질문 |
| vth | 전체 반환 | default 없음 |

사용자가 명시한 값은 절대 교정하지 않는다. 표준 triple은 빠진 axes를 채우는 용도지, 사용자가 명시한 값을 덮어쓰지 않는다. 사용자가 `vdd`(숫자)를 명시하면 `vdd_type` default는 스킵한다 (중복 필터 방지).

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

### analyze (tool, LLM + code sandbox)

- LLM이 분석용 Python 코드(pandas, scipy, matplotlib 등)를 생성한다.
- 생성된 코드를 샌드박스에서 실행하여 수치 결과와 차트를 반환한다.
- 시각화(차트)도 이 단계에서 코드로 생성한다. 별도 visualize 모듈 불필요.
- 차트는 base64 PNG로 반환한다.

### interpret (tool, LLM)

- 데이터 조회 결과 또는 분석 결과를 받아 도메인 맥락에서 해석한다.
- 두 가지 지식 소스를 결합하여 LLM에 전달한다:
  - **Domain Skill (정적 지식)**: 핵심 해석 규칙. 항상 주입.
  - **RAG retriever (동적 지식)**: 사내 RAG API를 통해 관련 문서 검색. (TODO: 엔드포인트 연결)
- analyze와 분리한 이유: analyze는 계산(범용), interpret는 해석(도메인 특화). 도메인 확장 시 analyzer는 재사용하고 interpret의 Skill만 교체한다.

## DB 구성

- **Oracle DB**: PPA 데이터, PDK 버전 정보. query_data가 SQL로 조회.
- **SQLite mock DB** (개발용): 실제 스키마(PAVE_PDK_VERSION_VIEW, PAVE_PPA_DATA_VIEW) 기반. ORACLE_PASSWORD 미설정 시 자동 사용.
- **RAG**: 사내 시스템에서 인덱스 생성/벡터 DB 관리. 이 프로젝트에서는 retriever로 데이터를 가져오기만 한다.

## 도메인 지식 주입

### 정적 지식: Skills

- **SQL Skill**: 뷰 스키마, SQL 템플릿, 캐시 설정, 엔티티 매핑 규칙 → query_data가 파싱
- **Analysis Skill**: 분석 패턴, 코드 생성 컨벤션, 데이터 전처리 규칙 → analyze 프롬프트에 주입
- **Domain Skill**: 핵심 해석 규칙, 파라미터 범위별 의미, 판단 기준 → interpret 프롬프트에 주입

### 동적 지식: RAG

사내 RAG 시스템이 인덱스 생성, 벡터 DB 저장, 검색을 담당한다. pave-agent는 retriever를 통해 API를 호출하여 관련 문서 조각을 가져온다.

## 확장

새로운 도메인 추가 시:
1. SQL Skill 작성 (뷰 스키마, SQL 템플릿, 캐시 설정, 엔티티 매핑)
2. Analysis Skill 작성 (분석 컨벤션)
3. Domain Skill 작성 (핵심 해석 규칙)
4. agent.py의 오케스트레이터 instruction 작성
5. tools/ 코드 수정 불필요

### 엔진과 Skill의 분리

| 도구 | 엔진 (코드) | Skill (지식) |
|------|-------------|-------------|
| query_data | SQL 파싱, 바인딩, 캐시, DB 호출 | 테이블 스키마, SQL 템플릿, 캐시 대상, 엔티티 매핑 |
| analyze | LLM 호출, 코드 추출, 샌드박스 실행 | 코드 생성 컨벤션, 분석 패턴, 전처리 규칙 |
| interpret | LLM 호출, RAG 연결, 프롬프트 조립 | 파라미터 해석 규칙, 코너 의미, 트레이드오프 |

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