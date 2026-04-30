# Use Case #1 — Direct Data Access

**Status**: spec LOCKED v1 (사용자 확정 — 2026-04-30)
**Source**: `memory/project_usecases.md` use case #1 ("직접 데이터 조회")

## 목적

사용자가 PDK 버전 + PVT/cell 조건 + metric 을 명시해 단일 데이터 포인트를 조회. 분석 / 비교 / 도메인 해석 불필요.

## Trigger 질문 예시

> "SF3 EVT1 PDK v1.0의 SSPG/0.54V/-25°C에서 LVT 주파수가 얼마야?"

## 동작 spec

### Turn 1 — 의도 파악 + 누락 항목 보충

**Entity 추출**
- process / mask / hspice ("v1.0")
- corner / vdd / temp / vth
- 사용자 요청 metric (예: 주파수 → FREQ_GHZ)

**행동**: ch_type 누락이면 tool 호출 없이 사용자에게 질문.
> "어떤 cell height type 으로 보여드릴까요? HD, HP, uHD"

근거: ch_type 은 default 없음. 잘못된 데이터 보여주는 것보다 묻는 게 옳음.

### Turn 2 — 사용자가 ch_type 답함 (예: "HP")

**Tool 1**: PDK 해결
```
query_versions(process="SF3", mask="EVT1", hspice="v1.0")
```

매칭 결과:
- 1건 → `auto_selected_pdk_id` 자동 사용
- 여러 건 → 사용자에게 PDK 버전 표 (현 prompts.py 의 PDK 버전 표시 규칙) + 선택 요청

**Tool 2**: 데이터 조회
```
query_ppa(
    pdk_id=<resolved>,
    corner="SSPG", temp=-25, vdd=0.54, vth="LVT", ch_type="HP",
    metrics=["FREQ_GHZ"]
)
```

`metrics` 인자로 응답 표 컬럼을 사용자 요청 metric 으로 필터링 (focus principle, 코드가 처리).

**호출하지 않는 것**: analyze, interpret (단순 조회라서).

### 응답 구조 (5 블록 순서)

1. **PDK 버전 정보 표** — 코드 산출 (`pdk_info` 기반)
   ```
   | PROCESS | PROJECT_NAME | MASK | DK_GDS | VDD_NOM | HSPICE | LVS | PEX |
   ```

2. **Search conditions 표** — 코드 산출 (compact key-value 한 줄)
   ```
   | corner | temp | vdd | vth | cell | ds | wns | ch_type |
   |--------|------|-----|-----|------|-----|-----|---------|
   | SSPG | -25 | 0.54 | LVT | AVG(INV,ND2,NR2) | AVG(D1,D4) | N4 | HP |
   ```

3. **applied_defaults 자연어 안내** — orchestrator 가 작성
   > "cell 은 AVG(INV,ND2,NR2), ds 는 AVG(D1,D4) 평균이 적용됐고 wns 는 config default 입니다. 다른 조건 보고 싶으시면 말씀해주세요."

4. **데이터 테이블** — 코드 산출 (FREQ_GHZ 컬럼만, markdown 그대로)

5. **답변 summary** — orchestrator 가 데이터 테이블에서 한 줄 읽음
   > "FREQ = 4.52 GHz"

## 핵심 설계 원칙 (이 케이스에서 작동하는 것)

- **숫자는 코드가 처리**: PDK 정보 표, search conditions 표, 데이터 테이블 모두 코드 산출. LLM 은 raw 숫자 변환·재계산 X.
- **LLM 의 역할 한정**: 의도 분류 (어떤 metric 요청? 누락 항목 뭐?) + 자연어 안내 (applied_defaults 설명) + 표에서 단일 값 1줄 옮기기 (summary).
- **단순 조회는 단순하게**: analyze / interpret 호출 안 함 → 빠름, 토큰 절약.

## 필요한 코드 변경 (현재 미구현)

| # | 변경 | 파일 | 영향 |
|---|------|------|------|
| 1 | `query_versions` 에 `hspice` (그리고 `lvs`, `pex`) 인자 추가 | `pave_agent/tools/query_data.py` | "v1.0" 같은 도구 버전 사용자 표현 매칭 가능 |
| 2 | `query_ppa` 에 `metrics: list[str] \| None` 인자 추가. `_format_table` 이 metric 컬럼 필터링 | `pave_agent/tools/query_data.py` | 응답 표가 사용자 요청 metric 만 포함 (focus principle, 코드가 처리) |
| 3 | `query_ppa` 응답에 `search_conditions_table` 필드 (compact key-value markdown) | `pave_agent/tools/query_data.py` (신규 헬퍼 `_format_search_conditions`) | 응답 5 블록 중 2번째 |
| 4 | `prompts.py` 에 응답 5 블록 순서 명시 + 단순 조회는 analyze/interpret X 명시 | `pave_agent/prompts.py` | 미세 조정 |

## Edge cases

- **PDK 매칭 0건**: `query_versions` 가 빈 결과. orchestrator 는 사용자에게 "조건에 맞는 PDK 가 없습니다. 가능한 버전: ..." 안내.
- **PDK 매칭 여러 건**: 표 + 사용자 선택 (현 prompts.py 규칙).
- **사용자가 raw vdd 줌**: `vdd_type` default 자동 skip (이미 query_ppa 처리).
- **사용자가 metric 명시 안 함**: `metrics=None` → 모든 metric 컬럼 포함.
- **데이터 0행** (조건이 mock/실제 DB 와 안 맞음): `table` 이 "(데이터 없음)" — 사용자에게 그대로 안내.

## EvalSet 케이스 (자동 검증)

`tests/agent/eval_sets/direct_data_access.evalset.json`

위 spec 의 happy path 가 그대로 EvalSet 에 박힘. `final_response` 는 placeholder — 사내 vLLM 첫 응답 보고 다듬기.

## Backlog / open

- `metrics` 인자가 `list` 면 여러 metric 가능. 사용자가 "주파수와 power 보여줘" 같은 multi-metric 요청 시 그대로 동작.
- summary 의 "한 줄" 형식 — 단위 포함 여부, 조건 같이 표시할지 (예: "0.54V LVT 에서 FREQ = 4.52 GHz"). 일단 가장 단순한 "FREQ = X GHz" 로.
- `search_conditions_table` 의 컬럼 순서 / 라벨 한국어로 할지 영어 그대로 할지.
