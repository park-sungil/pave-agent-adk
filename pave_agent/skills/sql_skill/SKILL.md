---
name: sql_skill
description: DB 뷰 스키마, SQL 템플릿, 엔티티 매핑 규칙을 정의한다. query_data tool이 SQL을 조립할 때 참조한다.
---

# SQL Skill

## Views

### PAVE_PDK_VERSION_VIEW (PDK 버전 정보)

| Column | Type | Description |
|--------|------|-------------|
| PAVE_PDK_ID | NUMBER | PDK 고유 ID (PK) |
| PROCESS | VARCHAR2 | 공정명 (e.g., LN04LPP, LN04LPE, SF3) |
| PROJECT | VARCHAR2 | 프로젝트 코드 (e.g., S5E9945) |
| PROJECT_NAME | VARCHAR2 | 프로젝트 별명 (e.g., Solomon, Thetis) |
| MASK | VARCHAR2 | 마스크 버전 (e.g., EVT0, EVT1) |
| DK_GDS | VARCHAR2 | DK GDS |
| IS_GOLDEN | NUMBER(1) | Golden PDK 여부 (0 또는 1) |
| VDD_NOMINAL | NUMBER | nominal voltage |
| HSPICE | VARCHAR2 | HSPICE 도구 버전 |
| LVS | VARCHAR2 | LVS 도구 버전 |
| PEX | VARCHAR2 | PEX 도구 버전 |
| CREATED_AT | DATE | 생성일 |
| CREATED_BY | VARCHAR2 | 생성자 |

### PAVE_PPA_DATA_VIEW (셀 레벨 PPA 측정 데이터)

| Column | Type | Description |
|--------|------|-------------|
| PDK_ID | NUMBER | FK → PAVE_PDK_VERSION_VIEW.PAVE_PDK_ID |
| CELL | VARCHAR2 | 셀 타입 (INV, ND2, NR2) |
| DS | VARCHAR2 | Drive Strength (D1, D2, D3, D4) |
| CORNER | VARCHAR2 | Process corner (TT, FF, SS, SF, FS, SSPG) |
| TEMP | NUMBER | 측정 온도 (°C) |
| VDD | NUMBER | 공급 전압 (V) |
| VTH | VARCHAR2 | Threshold Voltage 타입 (ULVT, SLVT, LVT, MVT, RVT, HVT) |
| WNS | VARCHAR2 | Nanosheet Width (N1~N5) |
| WNS_VAL | NUMBER | Nanosheet Width 값 (nm) |
| CH | VARCHAR2 | Cell Height (e.g., CH138, CH168, CH200) |
| CH_TYPE | VARCHAR2 | Cell Height 타입 (uHD, HD, HP) |
| FREQ_GHZ | NUMBER | RO 발진 주파수 (GHz) — 성능 대표 지표 |
| D_POWER | NUMBER | 동적 전력 (mW) |
| D_ENERGY | NUMBER | 1회 switching 에너지 |
| ACCEFF_FF | NUMBER | AC Effective Capacitance (fF) |
| ACREFF_KOHM | NUMBER | AC Effective Resistance (kΩ) |
| S_POWER | NUMBER | 정적(누설) 전력 (mW) |
| IDDQ_NA | NUMBER | IDDQ 누설전류 (nA) |

## 조인 관계

```sql
-- 두 View 조인
SELECT v.PROJECT, v.MASK, d.CELL, d.FREQ_GHZ
FROM PAVE_PPA_DATA_VIEW d
JOIN PAVE_PDK_VERSION_VIEW v ON d.PDK_ID = v.PAVE_PDK_ID
WHERE v.PROJECT = :project
```

## SQL Templates

### single_cell
```sql
SELECT d.CELL, d.DS, d.CORNER, d.TEMP, d.VDD, d.VTH,
       d.FREQ_GHZ, d.D_POWER, d.D_ENERGY, d.ACCEFF_FF, d.ACREFF_KOHM,
       d.S_POWER, d.IDDQ_NA, d.WNS, d.CH, d.CH_TYPE
FROM PAVE_PPA_DATA_VIEW d
JOIN PAVE_PDK_VERSION_VIEW v ON d.PDK_ID = v.PAVE_PDK_ID
WHERE v.PROJECT = :project
  AND d.CELL = :cell
  {pdk_clause}
ORDER BY d.CELL, d.CORNER
```

### compare_cells
```sql
SELECT d.CELL, d.DS, d.CORNER, d.TEMP, d.VDD, d.VTH,
       d.FREQ_GHZ, d.D_POWER, d.S_POWER, d.IDDQ_NA
FROM PAVE_PPA_DATA_VIEW d
JOIN PAVE_PDK_VERSION_VIEW v ON d.PDK_ID = v.PAVE_PDK_ID
WHERE v.PROJECT = :project
  AND d.CELL IN ({cell_placeholders})
  {pdk_clause}
ORDER BY d.CELL, d.DS
```

### trend
```sql
SELECT v.PAVE_PDK_ID, v.MASK, v.HSPICE, v.CREATED_AT,
       d.CELL, d.DS, d.CORNER, d.TEMP, d.VDD,
       d.FREQ_GHZ, d.D_POWER, d.S_POWER, d.IDDQ_NA
FROM PAVE_PPA_DATA_VIEW d
JOIN PAVE_PDK_VERSION_VIEW v ON d.PDK_ID = v.PAVE_PDK_ID
WHERE v.PROJECT = :project
  AND d.CELL = :cell
ORDER BY v.CREATED_AT, d.CELL
```

## Entity Mapping

| 사용자 표현 | 매핑 대상 | 예시 |
|-------------|-----------|------|
| 공정, 공정명, 프로세스 | PROCESS | LN04LPP, LN04LPE, SF3 |
| 프로젝트, 과제 | PROJECT / PROJECT_NAME | S5E9945, Solomon |
| 마스크 | MASK | EVT0, EVT1 |
| 셀, 셀 타입 | CELL | INV, ND2, NR2 |
| DS, 드라이브 스트렝스 | DS | D1, D2, D3, D4 |
| 코너, 공정 코너 | CORNER | TT, FF, SS |
| 온도 | TEMP | -25, 25, 125 |
| 전압, VDD | VDD | 0.5, 0.72, 0.75 |
| Vth 타입 | VTH | ULVT, SLVT, LVT, MVT, RVT, HVT |
| 주파수, freq | FREQ_GHZ | |
| 동적 전력, d_power | D_POWER | |
| 정적 전력, 누설 전력, s_power | S_POWER | |
| IDDQ, 누설전류 | IDDQ_NA | |

## Cache

소량 테이블은 최초 1회 전체 조회 후 캐싱하여 이후 Python 필터링으로 대체한다.

| 테이블 | 필터 컬럼 |
|--------|-----------|
| PAVE_PDK_VERSION_VIEW | PROJECT, PROJECT_NAME |

## 주의사항
- PDK ID 미지정 시 IS_GOLDEN = 1 인 golden PDK를 기본으로 사용
- PPA 비교 시 반드시 동일 PVT corner (CORNER, VDD, TEMP) 조건 확인
