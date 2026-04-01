---
name: domain_skill
description: 반도체 PPA 데이터의 도메인 해석 규칙을 정의한다. interpret tool이 분석 결과를 해석할 때 항상 참조하는 핵심 규칙이다.
---

# Domain Skill — 반도체 PPA 해석 규칙

## 핵심 파라미터 해석

### VTH (문턱 전압, Threshold Voltage)
- **정상 범위**: 공정별 타겟 ± 10% 이내
- **낮은 VTH (타겟 대비 -15% 이하)**: 누설 전류(IOFF) 증가 우려. SCE(Short Channel Effect) 가능성 검토 필요
- **높은 VTH (타겟 대비 +15% 이상)**: 구동 전류(ION) 감소, 속도 저하 우려
- **코너 민감도**: SS 코너에서 VTH가 가장 높고, FF 코너에서 가장 낮음

### ION (온 전류, On-state Current)
- **높을수록 좋음**: 스위칭 속도와 직결
- **ION/IOFF 비율**: 10^4 이상이 일반적으로 양호
- **코너별 해석**: FF에서 최대, SS에서 최소

### IOFF (누설 전류, Off-state Current)
- **낮을수록 좋음**: 전력 소비와 직결
- **급격한 IOFF 증가**: GIDL(Gate-Induced Drain Leakage) 또는 SCE 의심
- **온도 의존성**: 고온(125°C)에서 IOFF가 크게 증가하는 것은 정상적 경향

### CGATE (게이트 캐패시턴스)
- **낮을수록 좋음**: 동적 전력 소비 감소
- **VTH-CGATE 트레이드오프**: CGATE를 줄이면 VTH 제어가 어려워질 수 있음

## 공정 코너 해석

| 코너 | NMOS | PMOS | 특성 |
|------|------|------|------|
| TT | Typical | Typical | 기준 동작점 |
| FF | Fast | Fast | 최고 속도, 최대 누설 |
| SS | Slow | Slow | 최저 속도, 최소 누설 |
| SF | Slow | Fast | NMOS 느림, PMOS 빠름 |
| FS | Fast | Slow | NMOS 빠름, PMOS 느림 |

## 트렌드 해석 규칙

- **버전 간 VTH 감소 트렌드**: 공정 최적화 또는 SCE 악화 가능성. ION/IOFF 함께 확인 필요
- **버전 간 IOFF 증가 트렌드**: 누설 제어 악화. 게이트 스택 또는 도핑 프로파일 점검 필요
- **코너 간 spread 증가**: 공정 변동성 증가 의미. 수율 영향 검토 필요

## PPA 트레이드오프 규칙

- **Performance ↔ Power**: ION 증가(속도↑)는 대부분 IOFF 증가(누설↑)를 수반
- **Performance ↔ Area**: 셀 면적 축소는 SCE로 인한 VTH 변동 증가 가능
- **최적화 방향 판단**: 사용자의 설계 목적(고성능/저전력/균형)에 따라 해석 관점을 조정

## 해석 응답 가이드

1. **수치 제시**: 핵심 수치를 먼저 요약한다.
2. **비교 맥락**: 타겟 대비, 이전 버전 대비, 코너 간 비교 맥락을 제공한다.
3. **의미 해석**: 수치가 설계에 미치는 영향을 설명한다.
4. **권장 사항**: 추가 확인이 필요한 사항이 있으면 제안한다.
