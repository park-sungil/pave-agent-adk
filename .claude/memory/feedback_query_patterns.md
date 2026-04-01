---
name: query pattern rules
description: 사용자 질문 패턴과 데이터 조회 규칙. 잘못된 가정 방지용.
type: feedback
---

1. 사용자는 "SF3 EVT1" 같이 process + mask로 물어보지 않는다. "Thetis EVT0", "Thetis EVT1" 같이 project_name + mask로 물어본다.

2. 전체 데이터를 필터 없이 가져오면 UI가 터질 수 있다. 조건 없이 조회할 때 기본 조건이 필요하지만, 아직 결정되지 않음 (TODO).

**Why:** langgraph에서는 TT/25°C/nominal VDD가 기본이었지만, ADK에서 이 규칙을 그대로 쓸지 추후 논의 필요.
**How to apply:** instruction에서 "전체 데이터 반환"이라고 안내하지 말 것. 기본 조건 규칙이 정해질 때까지 보류.
