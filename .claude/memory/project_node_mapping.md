---
name: process node mapping
description: 공정 노드(2nm, 3nm)와 process명(SF2, SF3 등) 매핑. DB에 없는 정보이므로 별도 관리 필요.
type: project
---

사용자는 "2nm", "3nm" 같은 공정 노드로 질문할 수 있지만, DB 테이블에는 PROCESS 컬럼에 SF3, LN04LPP 같은 코드명만 있다.

| 공정 노드 | PROCESS 코드 |
|-----------|-------------|
| 2nm | SF2, SF2P, SF2PP |
| 3nm | SF3 |

**Why:** 사용자 발화의 "2nm"를 적절한 PROCESS 코드로 매핑해야 함.
**How to apply:** instruction 또는 sql_skill에 매핑 테이블로 기술. 향후 추가 공정 시 업데이트.
