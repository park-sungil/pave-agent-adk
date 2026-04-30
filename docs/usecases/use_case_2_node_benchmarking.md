# Use Case #2 — Node Benchmarking

**Status**: spec LOCKED v1 (사용자 확정 — 2026-04-30)
**Source**: `memory/project_usecases.md` use case #2 ("N vs N-1 benchmarking")

## 목적

사용자가 두 process node (예: 2nm vs 3nm) 의 PPA 변화율을 동일 PVT/cell/vth 조건에서 비교. 분석 (delta/pct) + 도메인 해석 (technical insight) 모두 필요.

## Trigger 질문 예시

> "SSPG/0.54V/-25°C에서 3nm 대비 2nm LVT 주파수가 어떻게 변해?"

(orientation: "**3nm 대비 2nm**" → 베이스라인 = 3nm, 변화 = 2nm 값 기준 pct.)

## 동작 spec

### Turn 1 — 의도 파악 + 누락 보충

**Entity 추출**
- corner / vdd / temp / vth
- 베이스라인 node, 비교 대상 node (예: baseline=3nm, target=2nm)
- 사용자 요청 metric (예: 주파수 → FREQ_GHZ)

**행동**: ch_type 누락이면 tool 호출 없이 사용자에게 질문. (#1 과 동일 패턴)
> "어떤 cell height type 으로 보여드릴까요? HD, HP, uHD"

### Turn 2 — 사용자 ch_type 답함 (예: "HP")

**Tool calls** (병렬 가능)
- `query_versions(node="3nm")` — baseline node PDK 후보
- `query_versions(node="2nm")` — target node PDK 후보

**PDK 해결 처리**
- 1개 매칭 → `auto_selected_pdk_id` 사용
- 여러 매칭 → 해당 node 의 PDK 표 + 사용자 선택 요청

응답 예: "3nm 은 자동 선택 (Solomon EVT1). 2nm 은 다음 중 선택해주세요: ... 표 ..."

### Turn 3 — 사용자가 2nm PDK 선택 (예: "Vanguard EVT0")

**Tool calls** (순서)
1. `query_ppa(pdk_id=<3nm>, corner, temp, vdd, vth, ch_type, metrics=["FREQ_GHZ"])` — baseline
2. `query_ppa(pdk_id=<2nm>, corner, temp, vdd, vth, ch_type, metrics=["FREQ_GHZ"])` — target
3. `analyze(pdk_ids=[<3nm>, <2nm>], analysis_request="...", baseline_pdk_id=<3nm>)` — benchmark fast path 작동, deterministic
4. `interpret(pdk_ids=[<3nm>, <2nm>], question="...")` — Technical Insight 생성

### 응답 구조 (7 블록 — full)

1. **PDK 버전 정보 표** (양쪽 PDK 함께) — 코드 산출
2. **Search conditions 표** — 코드 산출 (compact key-value, #1 동일 형식)
3. **applied_defaults 자연어 안내** — orchestrator
4. **데이터 테이블** — 코드 산출 (양쪽 PDK 의 metric 값 raw)
5. **Ratio 표** — analyze 산출. Transposed layout: PDK A / PDK B / Ratio 행, 변하는 axis (VTH 등) 컬럼. **절대 delta 표시 X — pct 만**.

   ```
   **FREQ_GHZ** (axis: VTH)
   | | ULVT | SLVT | LVT | MVT | RVT | HVT |
   | PDK A | 4.72 | 4.39 | 3.77 | 3.44 | 3.07 | 2.70 |
   | PDK B | 4.51 | 4.16 | 3.60 | 3.28 | 2.91 | 2.59 |
   | Ratio | -4.43% | -5.41% | -4.57% | -4.61% | -5.08% | -3.98% |
   ```

   metric 이 여러 개면 metric 마다 한 표씩 (multi-metric 변형 케이스).
6. **Technical Insight** — interpret 산출 (5 rubric 항목 포함, 아래 참조)
7. **답변 summary** — orchestrator 가 1줄 요약 ("2nm 가 3nm 대비 +5.2% 빨라짐" 정도)

## Technical Insight rubric (도메인 지식 기반)

`pave_domain.md` 의 §3, §4.5, §5, §6 추론. 비교/분석 케이스 전반에 재사용 가능.

### 5 항목

| # | 항목 | 도메인 근거 (pave_domain.md) | 검증 방식 |
|---|------|------------------------------|----------|
| 1 | **change_quantification** | §4.5 RO freq = 공정 성능 대표 지표 | mechanical (ratio/pct 형식 매칭) |
| 2 | **measurement_context** | §6.3 worst-case corner 매핑 | LLM judge (의미 평가) |
| 3 | **causal_speculation** | §5 (설계 파라미터 영향), §6 (조건 상관관계) | LLM judge |
| 4 | **measurement_caveats** | §5.1 (drive strength), §5.4 (Vth temperature inversion) | mechanical (default 언급 substring) + LLM judge |
| 5 | **actionable_followup** *(optional)* | §5.1 D1/D4 분리, §6.1 다른 온도 점 | LLM judge |

### 항목별 의미

- **change_quantification**: 사용자 요청 metric 의 ratio (또는 pct). 정량 변화 없이 응답 X.
- **measurement_context**: 측정 조건의 의의. 예: "SSPG/-25°C/0.54V 는 GPU worst-case 시나리오와 유사".
- **causal_speculation**: 변화 원인을 도메인 메커니즘으로 추정. 예: "process scaling / Vth offset / Reff·Ceff 변화 / cell architecture / nanosheet width" 중 dominant 후보 제시.
- **measurement_caveats**: 측정 신뢰도/한계. 예: "cell 평균 + ds 평균 + default WNS 사용. cell-by-cell 변동 가능, Vth 종류별 temperature inversion 민감도 차이 있음".
- **actionable_followup**: 정밀 분석 위한 추가 조회/분석 제안. 예: "D1/D4 분리, 다른 PVT 점 추가 조회".

### 응답 형식 (LLM 자유, rubric 항목만 충족)

예시:

> **변화량**: 2nm Vanguard EVT0 은 3nm Solomon EVT1 대비 SSPG/-25°C/0.54V/LVT 조건에서 FREQ +5.2% 향상.
>
> **측정 조건**: SSPG/-25°C/0.54V 는 GPU worst-case 시나리오와 유사하며, low-temperature inversion 영향이 작은 LVT 셀 기준이라 직접 비교 가능.
>
> **원인 추정**: process scaling 효과가 dominant. Vth 종류는 동일 (LVT) 하나 nanosheet width / cell architecture 차이가 부수적 영향. Reff 감소가 주요 메커니즘으로 추정.
>
> **신뢰도/한계**: cell 평균 (INV/ND2/NR2) + ds 평균 (D1/D4) + ch_type 별 default WNS 사용 중. 단일 cell 또는 단일 ds 비교 시 ±2-3% 변동 가능.
>
> **추가 검토 (선택)**: D1/D4 분리하여 drive strength 영향 분석, 또는 -25°C/25°C/125°C 비교로 temperature inversion 영향 확인 권장.

## 필요한 코드 변경

(#1 과 공유)
| # | 변경 | 파일 |
|---|------|------|
| 1 | `query_versions` 에 `hspice/lvs/pex` 인자 | `tools/query_data.py` |
| 2 | `query_ppa` 에 `metrics` 인자 | `tools/query_data.py` |
| 3 | `query_ppa` 응답에 `search_conditions_table` 필드 | `tools/query_data.py` |

(#2 신규)
| # | 변경 | 파일 |
|---|------|------|
| 4 | `analyze.benchmark_delta` 가 `baseline_pdk_id` 인자 받기 (orientation 명시) | `tools/deterministic_analysis.py` + `tools/analyze.py` |
| 5 | `analyze` 의 `formatted_result` 가 ratio/pct 강조 (현재 Delta + pct 같이 표시 → pct 우선) | `tools/analyze.py::_format_benchmark` |
| 6 | `interpret` 프롬프트에 5 rubric 항목 명시 (자유 형식, 항목 충족) | `tools/interpret.py` 프롬프트 |
| 7 | `prompts.py` 에 응답 7 블록 순서 + 비교/분석 케이스에서 analyze + interpret 둘 다 호출 명시 | `pave_agent/prompts.py` |

## Edge cases

- **Mask 명시 안 됨, node 만 명시**: query_versions 가 해당 node 의 PDK 목록 반환. 여러 개면 사용자 선택. (#1 동일 패턴)
- **양쪽 노드 모두 1개 auto**: 사용자 추가 선택 없이 바로 Turn 3 진행 (이론적으로 Turn 2 → Turn 3 합쳐짐).
- **데이터 0행**: `query_ppa` 결과 비어 있으면 비교 불가능 → 사용자에게 "조건에 맞는 데이터 없음. 다른 조건?" 안내.
- **사용자가 명시한 vth 가 한쪽 PDK 에 없음**: 그 metric 비교 불가. 안내.

## EvalSet 케이스 (자동 검증)

`tests/agent/eval_sets/node_benchmarking.evalset.json`

위 spec 의 happy path. 3 turn 흐름 (clarification → PDK 선택 → 비교 결과). final_response 는 placeholder — 사내 vLLM 첫 응답 보고 다듬을 것.

## Variations

같은 카테고리 (node benchmarking) 내 변형. 동일 spec 적용 + 차이점만 메모.

### Variation 2A: Multi-metric + 부분 PVT + 전체 vth

**Trigger 질문 예시**:
> "2nm 와 3nm 노드 간의 동일 전압(0.7V) 대비 Freq 향상률과 Iddq 증가율을 비교해줘."

**기본 흐름과의 차이**:

| 측면 | 기본 (#2) | 2A |
|------|---------|-----|
| metric 개수 | 1 (FREQ_GHZ) | **2 이상** (FREQ_GHZ, IDDQ_NA, ...) |
| PVT 명시 | 다 명시 | **vdd 만** — corner=TT, temp=25 default 적용 |
| vth | 명시 (LVT) | **미명시 → 7 vth 모두 반환** (default 없음) |
| 비교 row 수 | 1 | **vth 별 7 행** |
| 방향 표현 | 중립 ("어떻게 변해") | **방향 명시** ("향상률" / "증가율") — orchestrator 가 사용자 어휘 그대로 응답에 사용 |

**Tool 인자 변화**:
- `query_ppa(..., metrics=["FREQ_GHZ", "IDDQ_NA"])` — list 인자
- `analyze(pdk_ids=[..., ...], analysis_request="동일 vdd 대비 FREQ 향상률 + IDDQ 증가율 비교", baseline_pdk_id=<3nm>)`

**응답 구조 변화** (블록 5 와 4 가 multi-row):
- 블록 4 (데이터 테이블): vth 7행 × (FREQ_3nm / FREQ_2nm / IDDQ_3nm / IDDQ_2nm) — 코드 산출
- 블록 5 (Ratio 표): metric 마다 한 표 (transposed layout, axis = VTH).
  ```
  **FREQ_GHZ** (axis: VTH)
  | | ULVT | SLVT | LVT | ... | HVT |
  | PDK A | ... | ... | ... | ... | ... |
  | PDK B | ... | ... | ... | ... | ... |
  | Ratio | +6.5% | +5.8% | +5.0% | ... | +3.2% |

  **IDDQ_NA** (axis: VTH)
  | | ULVT | SLVT | LVT | ... | HVT |
  | PDK A | ... |
  | PDK B | ... |
  | Ratio | +12% | +18% | +20% | ... | +45% |
  ```
- 블록 6 (Technical Insight) — 동일 5 rubric 적용. multi-vth 패턴 자체가 추가 통찰 (예: "HVT 의 IDDQ 증가율이 dominant — leakage scaling 이 process scaling 보다 큰 영향")
- 블록 7 (답변 summary): multi-metric 이라 1줄로 못 하면 2-3 줄 OK

**IDDQ 비교의 도메인적 의미** (`pave_domain.md` §7.5):
node 간 비교 시 IDDQ 는 "전력 특성 관점" — leakage 수준 = s_power 와 직접 상관. "결함" 관점 X.

## Edge case: Axis mismatch (VTH/WNS/등)

비교 시 두 PDK 의 어떤 axis (VTH, WNS, CELL, DS, CH) 가 다를 수 있다.

**처리 방식**: INNER (공통만 비교) + 명시적 caveat.

### `benchmark_delta` 의 동작

현재 pandas `merge()` 의 INNER JOIN — 공통 키만 비교 결과에 포함됨. silent drop.

**개선 (필요)**: `benchmark_delta` 가 `axis_coverage` 정보 추가 반환.

```python
{
    "comparison": [...],
    "summary": {...},
    "axis_coverage": {
        "VTH": {
            "common": ["ULVT", "SLVT", "LVT", "MVT", "RVT", "HVT"],
            "only_in_pdk_a": ["VLVT"],   # 3nm 에만
            "only_in_pdk_b": []
        },
        "WNS": {...},
        # ... 다른 axes
    }
}
```

### 응답에서 표시

차이 있을 때만 caveat 섹션 추가. 없으면 생략 (불필요한 noise X).

```
> 비교 가능 VTH: ULVT, SLVT, LVT, MVT, RVT, HVT (6개).
> **VLVT 는 3nm PDK 에만 있어 비교에서 제외**.
```

### 0건 비교 가능 시 (예: WNS 가 두 PDK 모두 default 인데 서로 달라서 매칭 0)

이건 일반 case 와 분리해서 명확한 에러 응답 + 가이드:
```
> 두 PDK 의 default WNS 가 달라서 (3nm: N3, 2nm: N4) 비교 가능 데이터가 없습니다.
> 동일 wns (예: wns="N4") 를 명시하시면 강제로 같은 wns 로 비교됩니다.
```

### 코드 변경 (axis mismatch 처리)

| 변경 | 파일 |
|------|------|
| `benchmark_delta` 가 `axis_coverage` 추가 반환 | `tools/deterministic_analysis.py` |
| `analyze._format_benchmark` 가 mismatch 있을 때만 caveat 섹션 추가 | `tools/analyze.py` |
| 0건 비교 시 명확한 에러 + 가이드 응답 | `tools/analyze.py` |

(이건 Variation 2A 뿐 아니라 모든 비교 케이스에 적용되는 일반 처리.)

## Backlog / open

- ratio vs pct 표시 형식 통일 — 현재 spec 은 pct 위주 (`+5.2%`). pure ratio (`1.052×`) 가 더 자연스러운 케이스 있을지 사내에서 검토.
- rubric items 의 phrasing 다듬기 — 사내 vLLM 응답 보고 어떤 표현이 잘 follow 되는지 calibration.
- Phase 3 LLM judge 시점에 각 rubric 항목별 threshold 결정.

## 재사용

위 5 rubric 은 비교/분석 케이스 전반 (use case #2, #3, #4, #5) 에 재사용 가능. 케이스마다 살짝 다른 강조점은 추가 rubric 으로 보충.
