---
name: pending decisions and TODOs
description: 현재 미결정 사항과 다음 작업 목록. 세션 시작 시 참조.
type: project
---

## 미결정 사항 (논의 필요)

- [ ] **기본 조건 규칙**: 사용자가 corner/temp/vdd를 명시하지 않았을 때 기본값을 적용할지, 어떤 값으로 할지. 전체 데이터 반환하면 UI가 터짐. langgraph에서는 TT/25°C/nominal VDD였으나 ADK에서 그대로 쓸지 미정.

## 이번에 할 작업

- [ ] **오케스트레이터 instruction 강화** (agent.py)
  - 공정 노드 매핑 반영 (2nm→SF2계열, 3nm→SF3)
  - 질문 패턴 수정 ("Thetis EVT0" 식, "SF3 EVT1" 아님)
  - 벤치마킹 흐름 (PDK A vs B → query 2번 → analyze → interpret)
  - 응답 톤 (evidence-first, conservative, DB 컬럼명 사용)
  - 기본 조건 규칙은 결정 후 반영

## 다음 세션: skill-generator와 함께

- [ ] **domain_skill 강화** ← pave-agent-langgraph/nodes/resources/pave_domain.md
- [ ] **sql_skill 강화** ← pave-agent-langgraph/nodes/resources/sql_patterns.md + AVG 처리 규칙
- [ ] **analysis_skill 강화** ← pave-agent-langgraph/nodes/analyzer.py 분석 모드
- [ ] **차트/시각화 검토** ← pave-agent-langgraph/nodes/visualizer.py
