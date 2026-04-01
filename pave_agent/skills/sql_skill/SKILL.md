---
name: sql_skill
description: Oracle DB 뷰 스키마, SQL 템플릿, 엔티티 매핑 규칙을 정의한다. query_data tool이 SQL을 조립할 때 참조한다.
---

# SQL Skill

## Views

### V_PPA_DATA (PPA 데이터 뷰)

| Column | Type | Description |
|--------|------|-------------|
| PROCESS_NODE | VARCHAR2(20) | 공정 노드 (e.g., N5, N3) |
| CELL_NAME | VARCHAR2(100) | 셀 이름 (e.g., INVD1, NAND2D1) |
| VERSION | VARCHAR2(50) | PDK 버전 |
| PARAM_NAME | VARCHAR2(50) | 파라미터 이름 (e.g., VTH, ION, IOFF, CGATE) |
| PARAM_VALUE | NUMBER | 파라미터 수치값 |
| PARAM_UNIT | VARCHAR2(20) | 단위 (e.g., V, A, F) |
| CORNER | VARCHAR2(20) | 공정 코너 (TT, FF, SS, SF, FS) |
| TEMPERATURE | NUMBER | 온도 (°C) |
| VOLTAGE | NUMBER | 전압 (V) |
| MEASURE_DATE | DATE | 측정일 |

### V_VERSION_INFO (버전 정보 뷰)

| Column | Type | Description |
|--------|------|-------------|
| PROCESS_NODE | VARCHAR2(20) | 공정 노드 |
| VERSION | VARCHAR2(50) | PDK 버전 |
| RELEASE_DATE | DATE | 릴리즈 일자 |
| STATUS | VARCHAR2(20) | 상태 (RELEASED, DRAFT, DEPRECATED) |
| DESCRIPTION | VARCHAR2(500) | 버전 설명 |

## SQL Templates

### 단일 셀 PPA 조회
```sql
SELECT PARAM_NAME, PARAM_VALUE, PARAM_UNIT, CORNER, TEMPERATURE, VOLTAGE
FROM V_PPA_DATA
WHERE PROCESS_NODE = :process_node
  AND CELL_NAME = :cell_name
  AND VERSION = :version
ORDER BY PARAM_NAME, CORNER
```

### 셀 비교 조회
```sql
SELECT CELL_NAME, PARAM_NAME, PARAM_VALUE, PARAM_UNIT, CORNER
FROM V_PPA_DATA
WHERE PROCESS_NODE = :process_node
  AND CELL_NAME IN (:cell_names)
  AND VERSION = :version
  AND PARAM_NAME IN (:param_names)
ORDER BY CELL_NAME, PARAM_NAME
```

### 버전별 추이 조회
```sql
SELECT VERSION, PARAM_NAME, PARAM_VALUE, MEASURE_DATE
FROM V_PPA_DATA
WHERE PROCESS_NODE = :process_node
  AND CELL_NAME = :cell_name
  AND PARAM_NAME IN (:param_names)
  AND MEASURE_DATE BETWEEN :start_date AND :end_date
ORDER BY MEASURE_DATE, PARAM_NAME
```

### 버전 목록 조회
```sql
SELECT VERSION, RELEASE_DATE, STATUS, DESCRIPTION
FROM V_VERSION_INFO
WHERE PROCESS_NODE = :process_node
  AND STATUS = :status
ORDER BY RELEASE_DATE DESC
```

## Entity Mapping

| 사용자 표현 | 매핑 대상 | 예시 |
|-------------|-----------|------|
| 공정, 공정 노드, 프로세스 | PROCESS_NODE | N5, N3, N7 |
| 셀, 셀 이름, 게이트 | CELL_NAME | INVD1, NAND2D1, DFFD1 |
| 버전, PDK 버전 | VERSION | v1.0, v2.1 |
| Vth, 문턱 전압 | PARAM_NAME='VTH' | |
| Ion, 온 전류 | PARAM_NAME='ION' | |
| Ioff, 누설 전류, 오프 전류 | PARAM_NAME='IOFF' | |
| Cgate, 게이트 캐패시턴스 | PARAM_NAME='CGATE' | |
| 코너, 공정 코너 | CORNER | TT, FF, SS |
| 온도 | TEMPERATURE | 25, -40, 125 |
