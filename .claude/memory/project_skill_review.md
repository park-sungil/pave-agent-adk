---
name: pave-skill review findings
description: skill-creator 기준 pave-skill 리뷰 결과. sql.md부터 수정 진행 중.
type: project
---

## sql.md
1. 불필요한 JOIN — _resolve_pdks가 pdk_id 확정 후 실행하므로 VERSION_VIEW JOIN 불필요. 에러 유발 확인됨
2. 3개 템플릿(single_cell, compare_cells, trend) 사실상 같은 쿼리 — 합칠 수 있음
3. "조인 관계" 섹션 — 코드에서 안 쓰는 참고용. 제거/축소 가능
4. Entity Mapping VDD 예시 — 0.5, 0.72, 0.75인데 실제 DB는 0.540~0.929

## analysis.md
5. 너무 일반적 — PDK 벤치마킹 delta, corner spread 등 도메인 특화 패턴 없음
6. 코너 목록 불일치 — TT, FF, SS, SF, FS인데 mock DB에는 TT, SSPG만 (실제 DB에는 더 있을 수 있음)

## interpretation.md
7. VLVT 누락 — VTH 목록에 없지만 DB에 있음
8. 코너 목록 — FF, SS, SF, FS 설명하지만 mock DB에는 TT, SSPG만

## SKILL.md
9. description이 너무 짧음 — 트리거 맥락 없음. skill-creator는 "pushy"하게 권장

**Why:** 실제 DB 데이터와 skill 문서 불일치로 에러 발생 + LLM에 잘못된 지식 전달
**How to apply:** sql.md → analysis.md → interpretation.md → SKILL.md 순서로 수정
