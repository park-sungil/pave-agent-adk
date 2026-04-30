# Phase 2/3 Roadmap

사내 vLLM 환경에서 진행할 EDD 다음 단계. 이 문서는 사용자 + 사내 Claude Code 의 작업 가이드.

## 현재 상태 (이번 세션 종료 시점)

✅ **Phase 1 (offline pytest)**: 28+ tests, ~7s, no LLM/no Oracle
- `tests/unit/`: 순수 함수 (`_resolve_pvt`, `select_sections`, `deterministic_analysis`)
- `tests/tool/`: 도구 contract (`query_ppa` needs_input/applied_defaults/state, `query_versions` 필터, analyze fast paths)
- `tests/test_analyze.py`, `tests/test_interpret.py`: legacy

⏳ **Phase 2 (`adk eval`)**: scaffold + 4 EvalSet skeletons
- `tests/agent/test_agent_eval.py`: pytest wrapper
- `tests/agent/test_config.json`: thresholds (`tool_trajectory_avg_score: 1.0`, `response_match_score: 0.4`)
- `tests/agent/eval_sets/`:
  - `ch_type_clarification.evalset.json` ← Anthropic 으로 검증됨 (PASSED)
  - `simple_freq_query.evalset.json` ← Anthropic 으로 부분 검증 (tool_traj 1.0 / response_match 0.386 — 표현 차이)
  - `direct_data_access.evalset.json` ← skeleton (final_response placeholder)
  - `node_benchmarking.evalset.json` ← skeleton
  - `ambiguous_pvt.evalset.json` ← skeleton

❌ **Phase 3 (rubric judge)**: 미시작

📦 **Documentation**:
- `tests/README.md`: 운영 reference
- `docs/edd-methodology.md`: EDD 철학 + 의사결정 log
- `docs/phase2-3-roadmap.md`: 이 문서

## 사내 환경 첫 세션 권장 순서

### Step 1: 환경 셋업 + 기본 동작 확인

```bash
# .env 변경
LLM_AUTH=header
LLM_API_BASE_HEADER=<사내 vLLM URL>
LLM_MODEL=<사내 모델 이름>
VLLM_DEP_TICKET=<...>
VLLM_SEND_SYSTEM_NAME=<...>
VLLM_USER_ID=<...>
VLLM_USER_TYPE=<...>

# Phase 1 그린 확인 (LLM 안 부름)
uv run --extra dev pytest -q
# 기대: 모든 unit + tool 테스트 통과
```

### Step 2: Phase 2 기존 케이스 사내 vLLM 으로 재실행

```bash
PAVE_REAL_LLM=1 uv run --extra dev pytest tests/agent -v
```

**기대되는 일들**:
- `ch_type_clarification`: Anthropic 에선 통과 — vLLM 에선 비결정성 더 높을 수 있음
- `simple_freq_query`: tool_trajectory 통과 가능성 ↑, response_match 는 거의 확실히 fail (LLM 응답 단어가 expected 와 다름)
- skeleton 들 (`direct_data_access`, `node_benchmarking`, `ambiguous_pvt`): `final_response` 가 placeholder 라서 response_match 무조건 fail. tool_trajectory 만 평가 가치 있음.

### Step 3: Threshold 재calibration

위 결과 보고:

1. **tool_trajectory 가 자주 fail**: 사내 모델이 instruction 잘 못 따름.
   - 해결 옵션 A: `num_runs=4` 로 smoothing
   - 해결 옵션 B: `tool_trajectory_avg_score` threshold 를 0.66 으로 (3 of 4 runs 일관성 요구)
   - 해결 옵션 C: 프롬프트 보강 (어느 부분이 ambiguous 한지 진단)

2. **response_match 가 자주 fail**: 어휘 차이가 큼.
   - 옵션 A: threshold 를 0.2-0.3 로 낮춤 (단순 sanity 만)
   - 옵션 B: `final_response_match_v2` (LLM judge) 로 교체. 사내 vLLM 이 judge 도 함. judge model quality 가 핵심.

   ```json
   // test_config.json 변경 예시
   "final_response_match_v2": {
     "threshold": 0.5,
     "judge_model_options": {
       "judge_model": "<사내 강한 모델 이름>"
     }
   }
   ```

### Step 4: EvalSet skeleton 의 `final_response` 채우기

각 skeleton 의 `final_response.parts[0].text` 가 placeholder. 실제 vLLM 응답 보고 채움:

```bash
# 예: direct_data_access 만 단독 실행해서 실제 응답 보기
PAVE_REAL_LLM=1 uv run --extra dev pytest \
  "tests/agent/test_agent_eval.py::test_agent_eval[direct_data_access]" \
  -s --tb=short
```

응답 캡처 후 EvalSet JSON 의 `final_response.parts[0].text` 에 비슷한 톤의 expected 박기.

### Step 5: 추가 케이스 작성

이미 있는 4개 외에 use case #3-5 (`memory/project_usecases.md`):

- **#3 Power efficiency**: "iddq 증가폭 대비 주파수 이득이 가장 큰 sweet spot 전압 구간은 어디야?"
  - 기대 흐름: query_ppa (전압 sweep) → analyze (slope 계산) → interpret
- **#4 Optimization strategy**: "성능 유지하면서 누설 전류 가장 적게 쓰는 flavor + vdd 조합"
  - 기대 흐름: query_ppa (다중 vth, vdd) → analyze (Pareto frontier) → interpret
- **#5 Parasitic analysis**: "LVT 성능이 떨어지는건 Reff 나 Ceff 중 어떤 영향?"
  - 기대 흐름: query_ppa (vth 변화) → analyze (ACREFF vs ACCEFF 분석) → interpret

`adk web` 에서 직접 질문하고 응답을 녹화 (`adk eval` UI) → JSON 자동 생성 → `eval_sets/` 에 떨어뜨림.

## Phase 3 도입 (Phase 2 안정 후)

### 후보 rubric

각 EvalSet 케이스의 `rubrics` 필드 또는 EvalCase-level 에 자연어 rubric 추가:

```json
{
  "eval_case": "...",
  "rubrics": [
    {
      "rubric_id": "focus_principle",
      "rubric_content": "응답에 사용자가 명시적으로 요청하지 않은 metric (예: D_POWER, S_POWER, IDDQ_NA 등) 이 포함되지 않는다."
    },
    {
      "rubric_id": "applied_defaults_disclosed",
      "rubric_content": "tool 응답에 applied_defaults 가 있을 때 사용자에게 자연어로 어떤 default 가 적용됐는지 알린다."
    },
    {
      "rubric_id": "korean_response",
      "rubric_content": "응답이 한국어로 작성되어 있다."
    }
  ]
}
```

벤치마킹 케이스 (`node_benchmarking`) 전용:
- "응답에 'Technical Insight' 또는 동등한 정성적 해석 섹션이 포함되어 있다."
- "Delta 표 또는 비교 표가 명시적으로 등장한다."

### test_config.json 변경

```json
{
  "criteria": {
    "tool_trajectory_avg_score": 1.0,
    "response_match_score": 0.3,
    "rubric_based_final_response_quality_v1": {
      "threshold": 0.7,
      "judge_model_options": {
        "judge_model": "<사내 강한 모델>"
      }
    }
  }
}
```

### Judge model 선택

ADK 내장 `rubric_based_final_response_quality_v1` 가 LLM judge 호출. quality 가 결과의 신뢰도 결정:
- 사내 vLLM 의 가장 큰 모델 사용 권장
- judge calibration: 사람이 정답 / 오답 라벨링한 5-10 케이스로 judge score 가 사람 판단과 일치하는지 1차 확인

## Backlog (별도 메모리에 박혀있는 항목)

| 항목 | 메모리 | 우선순위 |
|------|--------|---------|
| `compare_versions` 신규 tool | `feedback_micro_prompting.md` | 사내에서 필요시 |
| 차트 시각화 복귀 | `project_todo.md` | post-demo |
| RAG endpoint 연결 | `project_todo.md` | 사내 RAG 의존 |
| Langfuse + OTel binding | `project_observability.md` | production entry |

## 비용 가드레일

사내 vLLM 은 보통 무제한이지만 throughput 한계가 있음. EDD 실행 패턴:

- **dev loop**: Phase 1 (`pytest -q`) 매번. Phase 2 는 변경 영향 큰 곳만 (`pytest tests/agent -k <case>`).
- **PR 시점**: Phase 1 + Phase 2 schema 검증 (`tests/agent/test_evalset_schema_valid`). Phase 2 agent_eval 은 nightly.
- **Nightly**: Phase 2 전체 + (도입 후) Phase 3 rubric. 결과를 trend 그래프로.

## 회귀 발견 시 워크플로

1. Phase 2/3 가 회귀 발견
2. 원인 분석: 프롬프트 / 코드 / 데이터 / 모델 어디서?
3. 수정 + Phase 1 으로 contract 박제 (가능하면)
4. PR
5. 회귀 케이스가 영구히 가드 됨

## 도움 받을 곳

- EDD 철학: `docs/edd-methodology.md`
- 운영 reference: `tests/README.md`
- 작업 history: `git log` + `~/.claude/plans/cuddly-hugging-wadler.md`
- Use cases (Phase 2/3 케이스 시드): `memory/project_usecases.md`
