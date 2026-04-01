---
name: pave-agent use cases
description: 사용자가 정의한 pave-agent의 5가지 사용 목적과 5가지 질문 예시. 우선순위와 향후 확장 방향 결정 시 참조.
type: project
---

## 사용 목적 (5가지)

1. **Node migration assessment**: N vs N-1 RO 데이터 벤치마킹. PPA 이득이 공정 이동을 정당화하는지 판단.
2. **Worst case robustness**: Worst corner (SSPG/0.95V/125°C, SSPG/0.54V/-25°C) 데이터로 guardband(타이밍 마진) 산정.
3. **Power-performance optimization**: IDDQ vs freq 플롯에서 sweet spot 탐색. 주파수 최대화 + 누설전류 급증 이전 지점.
4. **Raw technology validation**: RO 시뮬레이션으로 공정의 intrinsic speed 검증. 복잡한 라이브러리 모델 이전의 순수 성능.
5. **Library strategy selection**: Cell height + VT flavor 비율 분석으로 프로젝트 타겟에 맞는 standard cell mix 결정.

## 질문 예시 (5가지)

1. **Direct data access**: "SF3 EVT1 PDK v1.0의 SSPG/0.54V/-25°C에서 LVT 주파수가 얼마야?"
2. **N vs N-1 benchmarking**: "2nm와 3nm 노드 간의 동일 전압(0.7V) 대비 freq 향상률과 iddq 증가율을 비교해줘."
3. **Power efficiency**: "iddq 증가폭 대비 주파수 이득이 가장 큰 sweet spot 전압 구간은 어디야?"
4. **Optimization strategy**: "성능을 유지하면서 누설 전류를 가장 적게 쓰는 flavor 및 vdd 조합은 뭐야?"
5. **Parasitic analysis**: "LVT 성능이 떨어지는건 Reff나 Ceff 중 어떤 영향이야?"

**Why:** 이 유스케이스가 instruction, skill, tool 설계의 기준이 됨.
**How to apply:** 새 기능 추가 시 이 유스케이스 중 어디에 해당하는지 확인. 우선순위: 1번(데이터 조회) + 2번(벤치마킹) 먼저, 나머지 점진적 추가.
