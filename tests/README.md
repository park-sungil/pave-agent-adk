# Tests

pave-agent의 EDD (Eval-Driven Development) 테스트 모음. 3-layer pyramid 구조로, 회귀를 가장 빠른 레이어에서 잡도록 설계.

## 빠른 실행

```bash
uv run --extra dev pytest -q                          # 기본 (34 tests, ~7s, 오프라인)
uv run --extra dev pytest tests/unit -q               # 순수 함수만
uv run --extra dev pytest tests/tool -q               # 도구 단위만
uv run --extra dev pytest tests/agent -q              # EvalSet schema 검증만 (LLM 안 부름)
PAVE_REAL_LLM=1 uv run --extra dev pytest tests/agent # real LLM 실행 (토큰 비용 발생)
```

EDD 철학 + 의사결정 log: [`docs/edd-methodology.md`](../docs/edd-methodology.md). 사내 환경 다음 단계: [`docs/phase2-3-roadmap.md`](../docs/phase2-3-roadmap.md).

## 레이어 구조

```
┌──────────────────────────────────────────────────┐
│ tests/agent/  — adk eval framework               │  Phase 2/3
│   EvalSet JSON × AgentEvaluator                  │  real LLM (gated)
├──────────────────────────────────────────────────┤
│ tests/tool/   — 도구 단위 (FakeToolContext)        │  Phase 1
│   no LLM, mock SQLite                            │
├──────────────────────────────────────────────────┤
│ tests/unit/   — 순수 함수                          │  Phase 1
│   no LLM, no DB                                  │
└──────────────────────────────────────────────────┘
```

같은 동작을 여러 레이어에 박제하지 말 것 — 가장 빨리 잡을 수 있는 레이어에만. Phase 2/3 가 회귀를 발견하면 Phase 1 으로 박제해서 재발 방지.

## 레이어별 책임

### `tests/unit/` — 순수 함수 (10 tests, ~ms)

외부 의존성 0. input → output.

| 파일 | 검증 대상 |
|------|----------|
| `test_domain_loader.py` | `select_sections` Section 0 항상 포함, 4개 cap |
| `test_deterministic_analysis.py` | `benchmark_delta`, `simple_stats`, `groupby_agg` 수학 |

(`_resolve_pvt` 는 PVT 단순화로 제거 — per-axis default 가 단순해서 inline 처리. 동작은 `tests/tool/test_query_ppa.py` 의 applied_defaults 검증으로 cover.)

**추가 기준**: 함수가 state/IO 없이 input → output 이면 여기. parametrize 적극 활용.

### `tests/tool/` — 도구 단위 (13 tests, ~6s)

ADK Tool 함수 (`query_ppa`, `query_versions`, `analyze`) 의 contract. `FakeToolContext` 로 ADK ToolContext 흉내, mock SQLite DB.

| 파일 | 검증 대상 |
|------|----------|
| `test_query_ppa.py` | `needs_input` 흐름, `applied_defaults` 의미, `table` 응답 / `data` 부재, 세션 state 캐시 키 |
| `test_query_versions.py` | `project_name` / `node` 필터, internal column 숨김 (PDK_ID/CREATED_AT/CREATED_BY), `pdk_id_by_idx` 매핑, `auto_selected_pdk_id` (결과 1개일 때) |
| `test_analyze_fast_paths.py` | 2-PDK 비교 / "평균" 키워드가 fast path 로 가서 LLM 안 부름 |

**추가 기준**: tool 응답 dict 의 키 이름, 세션 state 에 쓰는 키 이름은 다른 tool 들이 의존하는 contract. 그게 깨지면 회귀.

### `tests/agent/` — 에이전트 E2E

ADK `AgentEvaluator.evaluate_eval_set` 으로 진짜 agent 실행. EvalSet JSON 에 케이스 박제.

| 파일 | 역할 |
|------|------|
| `test_agent_eval.py` | pytest wrapper. 두 테스트: schema 검증 (항상 실행, ~0.16s), agent 실행 (`PAVE_REAL_LLM=1` gated) |
| `test_config.json` | metric threshold (`tool_trajectory_avg_score`, `response_match_score`) |
| `eval_sets/*.evalset.json` | 케이스 정의 |

**추가 기준**: 사용자가 실제로 묻는 질문 + 기대 동작. 자세한 작성법은 [EvalSet 작성](#evalset-작성-tests-agent) 참조. 현재 5개 케이스: ch_type_clarification (검증됨), simple_freq_query (부분 검증), direct_data_access / node_benchmarking / ambiguous_pvt (skeleton — 사내 vLLM 으로 final_response 채울 것).

### Legacy (변경 없음)

| 파일 | 검증 대상 |
|------|----------|
| `test_analyze.py` | 샌드박스 executor (5 tests) |
| `test_interpret.py` | RAG retriever fallback (1 test) |

## Mocking 규칙

### LLM

`pave_agent.llm.call_llm` 레벨에서 mock. **`litellm.completion` 직접 patch 하지 말 것** — ADK 의 `trace_call_llm` OTel span 이 끊기면 향후 Langfuse 연동 path 깨짐 (`project_observability.md` 참조).

```python
def test_no_llm_call(monkeypatch):
    monkeypatch.setattr(
        "pave_agent.llm.call_llm",
        lambda *a, **kw: pytest.fail("LLM was called"),
    )
    # ... 호출
```

### DB

`tests/conftest.py` 의 autouse fixture (`_reset_mock_db`) 가 `ORACLE_PASSWORD=""` 강제 + `mock.db` 삭제 → 매 세션 fresh seeded mock SQLite. 테스트 코드에서 별도 처리 불필요.

### ToolContext

`FakeToolContext` (`tests/conftest.py`). `state: dict` 만 노출, MagicMock 사용 X.

```python
def test_something(ppa_loaded_state):  # PDK versions + WNS config 미리 로드됨
    result = query_ppa(ppa_loaded_state, pdk_id=914, ch_type="HP")
```

## EvalSet 작성 (`tests/agent/`)

ADK 표준 JSON. 최소 구조:

```json
{
  "eval_set_id": "<slug>",
  "name": "<설명>",
  "description": "검증 의도. prompts.py 줄 번호 같은 근거 포함하면 좋음.",
  "eval_cases": [
    {
      "eval_id": "<case_slug>",
      "session_input": {
        "app_name": "pave_agent",
        "user_id": "test_user",
        "state": {}
      },
      "conversation": [
        {
          "invocation_id": "inv_0",
          "user_content": {
            "parts": [{"text": "<사용자 질문>"}],
            "role": "user"
          },
          "final_response": {
            "parts": [{"text": "<기대 응답>"}],
            "role": "model"
          },
          "intermediate_data": {
            "tool_uses": [
              {
                "name": "query_ppa",
                "args": {"pdk_id": 881, "ch_type": "HP"},
                "id": "call_1"
              }
            ],
            "tool_responses": []
          }
        }
      ]
    }
  ]
}
```

`tool_uses` 는 기대되는 tool 호출 sequence. 호출 없는 시나리오는 `[]`.

**작성 팁**: `adk web .` 띄우고 eval UI 에서 세션 녹화 → JSON 자동 생성. `eval_sets/` 에 떨어뜨리고 expected 부분만 다듬기.

**Threshold 조정** (`test_config.json`):
- `tool_trajectory_avg_score: 1.0` — tool 호출 sequence 정확히 일치해야 함
- `response_match_score: 0.4` — final response ROUGE-1 ≥0.4 (LLM 비결정성 흡수)

LLM 응답 톤이 자주 흔들리면 `response_match_score` 를 낮추거나 ADK 내장 `final_response_match_v2` (LLM judge) 로 교체.

## 트러블슈팅

| 증상 | 원인 / 해결 |
|------|------------|
| mock_db 관련 schema 에러 | `pave_agent/db/mock.db` stale. autouse fixture 가 정리 안 한 케이스 → 직접 삭제 후 재실행 |
| `pave_agent.agent` import 실패 | `pave_agent/__init__.py` 가 비어있음 — `agent_module="pave_agent.agent"` 그대로 쓸 것 (AgentEvaluator 가 `.agent` suffix 인식) |
| Phase 2 score 가 매번 다름 | LLM 비결정성. `test_config.json` 의 threshold 낮추거나 `num_runs` 늘림 |
| `ORACLE_PASSWORD` production 값 잡힘 | `.env` 가 conftest 보다 먼저 로드된 케이스. conftest 가 import 시점에 `os.environ` 덮어씀 + module attribute 도 강제. 그래도 안 되면 환경변수 직접 unset |

## 참고

- 전체 EDD 계획: `/Users/sungil/.claude/plans/cuddly-hugging-wadler.md`
- ADK eval framework 소스: `.venv/lib/python3.12/site-packages/google/adk/evaluation/`
- 메트릭 목록: `eval_metrics.py::PrebuiltMetrics`
