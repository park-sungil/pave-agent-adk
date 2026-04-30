# EDD (Eval-Driven Development) for pave-agent

테스트가 에이전트의 동작을 정의한다. 프롬프트가 정의하지 않는다.

## 왜 EDD

손으로 `adk web` 에서 질문 던지고 응답 보면서 프롬프트 손보는 방식은 4가지 실패 모드가 있다:

1. **느린 피드백**: 매 변경마다 사람이 눈으로 확인
2. **회귀 검출 안 됨**: X 고치면 Y 가 조용히 깨짐
3. **비결정성**: 같은 프롬프트에서 다른 출력
4. **drift**: 프롬프트가 비대해지면서 의도와 동작 괴리

EDD 는 4가지 모두 해결:

1. `pytest -q` 가 ~10초 안에 회귀 알려줌
2. 깨진 테스트가 회귀 표면화
3. threshold + multi-run 으로 노이즈 흡수
4. 테스트가 명세 — drift = 테스트 fail

## 3-layer pyramid

```
        ┌─────────────────────────────────────────┐
        │ tests/agent/  — adk eval framework      │  Phase 2/3
        │   real LLM (PAVE_REAL_LLM=1 gated)      │
        ├─────────────────────────────────────────┤
        │ tests/tool/   — 도구 단위                  │  Phase 1
        │   no LLM, mock SQLite                   │
        ├─────────────────────────────────────────┤
        │ tests/unit/   — 순수 함수                 │  Phase 1
        │   no LLM, no DB                         │
        └─────────────────────────────────────────┘
```

각 layer 가 잡는 회귀가 다름:

- **unit**: 순수 함수 정확성 (수학, 파싱, lookup)
- **tool**: 도구 contract (응답 dict 모양, 세션 state 부수효과)
- **agent**: orchestrator 의사결정 (어떤 tool, 어떤 인자, 응답 quality)

같은 동작을 여러 layer 에 박제하지 말 것. Phase 2 가 회귀 발견 → Phase 1 으로 옮겨 박제 (재발 방지). 회귀가 영구 가드 됨.

## 의사결정 log

### 왜 `pave_agent.llm.call_llm` 레벨에서 mock?

ADK 의 `google.adk.telemetry.tracing.trace_call_llm` 이 실 LLM 호출 주변에 OTel span 을 emit. `litellm.completion` 직접 patch 하면 이 span 이 안 찍힘. 향후 Langfuse 연동 시 span path 가 살아있어야 함 (`memory/project_observability.md`).

Trade-off: `analyze`/`interpret` 호출만 잡힘, orchestrator 는 못 잡음. Orchestrator-level 검증은 Phase 2 (`adk eval`) 가 담당.

### 왜 ADK 내장 `adk eval`?

ADK 가 이미 다음을 제공:
- `EvalSet` JSON 스키마 (`Invocation`, `IntermediateData` 등)
- `AgentEvaluator.evaluate_eval_set()` 실행기
- 내장 metric: `tool_trajectory_avg_score`, `response_match_score`, `final_response_match_v2`, `rubric_based_*`, `multi_turn_*`
- `adk web` UI 에서 EvalSet 녹화/편집

직접 만들면 위 모두 중복. Trade-off: ADK 의 metric 의미에 lock-in 되지만, 우리 needs 와 잘 매핑됨.

### 왜 `response_match_score: 0.4` (ROUGE-1)?

ROUGE-1 = unigram overlap. 빠르고 (LLM 호출 0), 단어 표현 변화에 민감. 0.4 면 "agent 가 응답 거부" (score~0) 는 잡고, 표현 차이는 흡수. 한국어 기술 응답은 의미 같아도 0.3-0.5 사이.

`final_response_match_v2` (LLM judge 의미 매칭) 로 전환할 시점:
- ROUGE 가 정상 응답에 자주 fail (false negative 많음)
- 비용 증가 OK (judge 호출 = +1 LLM round-trip 케이스당)
- `judge_model_options.judge_model` 설정 필요

### 왜 `num_runs=2` default?

ADK 기본값. LLM 비결정성을 한 번의 bad sample 로 fail 시키지 않게. `num_runs=4` 로 올리면 smoothing 미세 개선이지만 비용 2배. 특정 케이스가 일관되게 flake 하면 그 케이스만 별도 run 늘림.

## Mocking 규칙

| Layer | 대상 | 방법 |
|-------|------|------|
| Oracle DB | prod DB 없이 PPA 데이터 | autouse fixture `ORACLE_PASSWORD=""` 강제, `pave_agent/db/mock_db.py` 자동 사용 |
| `ToolContext` | `state: dict` 인터페이스 | `tests/conftest.py::FakeToolContext` (5줄) |
| `analyze`/`interpret` LLM | fast path 가 LLM 안 부르는지 검증 | `monkeypatch.setattr("pave_agent.llm.call_llm", ...)` |
| Orchestrator LLM (Phase 2) | 전체 agent 흐름 | `adk eval` 가 실 LLM 실행 (또는 추후 record/replay) |

## Threshold 튜닝 가이드

Phase 2 케이스가 fail 했을 때:

1. **Tool trajectory < threshold**: orchestrator 가 잘못된 tool 선택.
   - 일관됨 → 진짜 버그. 프롬프트/instruction 고침.
   - flaky → 비결정성. 프롬프트 명료화 또는 `num_runs` 증가.

2. **Response match < threshold**: 응답 표현이 expected 와 다름.
   - 먼저 확인: 응답이 의미상 맞는가? 직접 읽어볼 것.
   - 의미 맞고 표현만 다름 → `final_response.parts[0].text` 를 실제 응답에 가까운 단어로 다듬기, 또는 `final_response_match_v2` (LLM judge) 로 교체.
   - 진짜로 틀림 → 진짜 버그.

3. **threshold 낮춰서 fail 만 통과시키지 말 것.** 근원적 원인을 찾을 것.

## 비용 가이드 (대략 추정)

| 작업 | 토큰 | Anthropic 공개 가격 |
|------|------|--------------------|
| Phase 1 테스트 1개 | 0 | $0 |
| Phase 2 케이스 (1턴, num_runs=2) | ~10K input | ~$0.01 |
| Phase 2 케이스 (3턴, num_runs=2) | ~40K input | ~$0.04 |
| Phase 3 케이스 (LLM judge 포함) | +5-10K | +$0.005-0.01 |
| `adk web` 벤치마킹 1회 | varies | $0.05-0.20 / query |

사내 vLLM: per-token 비용 < 처리량 한계. 보통 무제한이지만 rate limit / queue depth 가 변수.

## 사내 vLLM 전환 시

`.env` 만 변경:

```bash
LLM_AUTH=header
LLM_API_BASE_HEADER=<사내 vLLM URL>
LLM_MODEL=<사내 모델>
VLLM_DEP_TICKET=<...>
VLLM_SEND_SYSTEM_NAME=<...>
VLLM_USER_ID=<...>
VLLM_USER_TYPE=<...>
```

`pave_agent/llm.py` 가 이미 header-based auth 를 처리함. 코드 변경 없음.

전환 후 동작 변화:
- Tool 선택: 일관성 ↓ → 강한 tool-use prompt 또는 `tool_choice` 강제
- 응답 표현: polish ↓ → `response_match_score` 재calibration
- 추론: robustness ↓ → 결정적 로직은 코드, 프롬프트는 의도 분류만

## "결정적 로직 코드 vs LLM 의도 분류" 원칙

micro-prompting (edge case마다 프롬프트에 규칙 추가) 은 지속 불가능 (`memory/feedback_micro_prompting.md`):
- 프롬프트 비대 → LLM attention 분산 → 이전 규칙 잊음
- 모델 의존성 ↑ → 약한 모델은 긴 rule list 못 따름
- 비가시성: `grep` 으로 prompt-driven 로직 추적 불가
- 비결정성: LLM 이 규칙을 확률적으로 따름

**규칙**: 동작 추가 시 먼저 묻기:
1. 이게 결정적인가? → 코드/tool 응답으로 처리
2. 판단이 필요한가? → 프롬프트

이 codebase 의 예:
- "PDK_ID 응답에서 숨겨" → `query_versions` 응답 필터로 이동 (결정적)
- "1개면 자동 선택" → 응답 dict 의 `auto_selected: True` 필드 (결정적)
- "사용자가 모호 입력 주면 되묻기" → 프롬프트 (판단)
- "벤치마킹 응답에 Technical Insight 포함" → 프롬프트 + Phase 3 rubric (판단)

## 도움 받을 곳

- 운영 reference (실행 방법): `tests/README.md`
- 다음 단계 구체 plan: `docs/phase2-3-roadmap.md`
- 작업 plan: `~/.claude/plans/cuddly-hugging-wadler.md`
- 메모리: `memory/feedback_micro_prompting.md` (원칙), `memory/project_observability.md` (Langfuse 방향)
