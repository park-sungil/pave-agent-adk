# SQL Skill

## Views

### ANTSDB.PAVE_PDK_VERSION_VIEW (PDK 버전 정보)

| Column | Type | Description |
|--------|------|-------------|
| PDK_ID | NUMBER | PDK 고유 ID (PK) |
| PROCESS | VARCHAR2 | 공정명 (e.g., SF3, SF2, SF2P, SF2PP) |
| PROJECT | VARCHAR2 | 프로젝트 코드 (e.g., S5E9955, S5E9965) |
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

### ANTSDB.PAVE_PPA_DATA_VIEW (셀 레벨 PPA 측정 데이터)

| Column | Type | Description |
|--------|------|-------------|
| PDK_ID | NUMBER | FK → ANTSDB.PAVE_PDK_VERSION_VIEW.PDK_ID |
| CELL | VARCHAR2 | 셀 타입 (INV, ND2, NR2) |
| DS | VARCHAR2 | Drive Strength (D1, D2, D4) |
| CORNER | VARCHAR2 | Process corner (TT, SSPG) |
| TEMP | NUMBER | 측정 온도 (°C) |
| VDD | NUMBER | 공급 전압 (V) |
| VTH | VARCHAR2 | Threshold Voltage 타입 (ULVT, SLVT, VLVT, LVT, MVT, RVT, HVT) |
| WNS | VARCHAR2 | Nanosheet Width (N1~N5) |
| WNS_VAL | NUMBER | Nanosheet Width 값 (nm) |
| CH | VARCHAR2 | Cell Height (e.g., CH138, CH148, CH168, CH200) |
| CH_TYPE | VARCHAR2 | Cell Height 타입 (uHD, HD, HP) |
| FREQ_GHZ | NUMBER | RO 발진 주파수 (GHz) — 성능 대표 지표 |
| D_POWER | NUMBER | 동적 전력 (mW) |
| D_ENERGY | NUMBER | 1회 switching 에너지 |
| ACCEFF_FF | NUMBER | AC Effective Capacitance (fF) |
| ACREFF_KOHM | NUMBER | AC Effective Resistance (kΩ) |
| S_POWER | NUMBER | 정적(누설) 전력 (mW) |
| IDDQ_NA | NUMBER | IDDQ 누설전류 (nA) |

## SQL Templates

PDK 선택(resolve_pdks)이 pdk_id를 확정한 뒤 PPA 데이터를 조회한다.
PDK당 전체 데이터를 1회 로드하여 세션에 캐싱하고, 이후 조건 필터링은 Python에서 수행한다.

### ppa_data
```sql
SELECT * FROM ANTSDB.PAVE_PPA_DATA_VIEW WHERE PDK_ID = :pdk_id
```

## Entity Mapping

| 사용자 표현 | 매핑 대상 | 예시 |
|-------------|-----------|------|
| 공정, 공정명, 프로세스 | PROCESS | SF3, SF2, SF2P, SF2PP |
| 프로젝트, 과제 | PROJECT / PROJECT_NAME | S5E9955, Solomon |
| 마스크 | MASK | EVT0, EVT1 |
| 셀, 셀 타입 | CELL | INV, ND2, NR2 |
| DS, 드라이브 스트렝스 | DS | D1, D2, D4 |
| 코너, 공정 코너 | CORNER | TT, SSPG |
| 온도 | TEMP | -25, 25, 125 |
| 전압, VDD | VDD | 0.540, 0.720, 0.880 |
| Vth 타입 | VTH | ULVT, SLVT, VLVT, LVT, MVT, RVT, HVT |
| 주파수, freq | FREQ_GHZ | |
| 동적 전력, d_power | D_POWER | |
| 정적 전력, 누설 전력, s_power | S_POWER | |
| IDDQ, 누설전류 | IDDQ_NA | |

## Cache

소량 테이블은 최초 1회 전체 조회 후 캐싱하여 이후 Python 필터링으로 대체한다.

| query_type | 테이블 |
|------------|--------|
| versions | ANTSDB.PAVE_PDK_VERSION_VIEW |

## PDK Version Structure & Selection Logic

### 컬럼 계층 구조
PROCESS (공정명, 예: SF3, SF2, SF2P, SF2PP)
  └─ 1:N ─► PROJECT / PROJECT_NAME (내부 코드 / 별명, 예: S5E9965 / Thetis)
                └─ 1:N ─► MASK (테이프아웃 단계, 예: EVT0, EVT1)
                              └─ 1:N ─► DK_GDS (디자인 킷 GDS 버전)
                                            └─ 1:N ─► HSPICE / LVS / PEX (도구 버전)

고유 PDK = (PROJECT, MASK, DK_GDS, HSPICE, LVS, PEX) 조합으로 식별

| 컬럼 | 의미 | 사용자 언급 빈도 |
|------|------|----------------|
| PROCESS | 공정명 (SF3, SF2, SF2P, SF2PP) | 높음 — 대화 진입점 |
| PROJECT | 내부 프로젝트 코드 (S5E9955, S5E9965…) | 낮음 |
| PROJECT_NAME | 프로젝트 별명 (Solomon, Thetis, Ulysses, Vanguard) | 중간 |
| MASK | 테이프아웃 단계 (EVT0, EVT1) | 중간 |
| DK_GDS | 디자인 킷 GDS 설정 | 낮음 |
| HSPICE / LVS / PEX | 도구 버전 — 하나라도 바뀌면 PPA 결과가 달라짐 | 낮음 |
| IS_GOLDEN | 관리자가 지정한 대표 버전 플래그 | 사용자가 직접 언급 안 함 — 자동 적용 |
| VDD_NOMINAL | 공칭 동작 전압 | 낮음 |
| CREATED_AT | 행 생성 타임스탬프 | 사용자 언급 안 함 — 중복 제거용 |

### IS_GOLDEN 범위
IS_GOLDEN=1은 (PROJECT, MASK, DK_GDS) 조합당 1개 존재. 해당 조합의 HSPICE/LVS/PEX 변형 중 대표 버전을 지정.

### PDK 선택 규칙
Step 1 — PROCESS / PROJECT / PROJECT_NAME / MASK / DK_GDS로 1차 필터링 (캐시에서 인메모리).
Step 2 — HSPICE/LVS/PEX를 사용자가 명시한 경우:
  - 해당 도구 버전으로 필터링
  - 동일 6-tuple에 여러 행이면 → CREATED_AT 최신 1개 선택
  - 정확히 1행 반환
Step 3 — HSPICE/LVS/PEX 미명시 (일반적 케이스):
  - IS_GOLDEN=1 행만 반환 (DK_GDS 변형별 1개)
  - IS_GOLDEN=1이 없으면 → 남은 전체 행 반환 (사용자가 대화형으로 선택)

### 사용자 인터랙션 트리거 조건
위 규칙 적용 후에도 후보가 여러 개일 때만 테이블을 보여준다
(PROCESS, PROJECT_NAME, MASK, DK_GDS, HSPICE, LVS, PEX 컬럼 표시).
즉, 동일 (PROJECT, MASK)에 DK_GDS 변형이 여러 개이고 각각 IS_GOLDEN이 있는 경우.

### 반환 형식
- 1행 → 확정, PDK_ID로 PPA 데이터 조회
- 여러 행 → 후보 목록 반환, 오케스트레이터가 사용자에게 선택 요청
- 0행 → 에러 + 가능한 옵션 제시

## 주의사항
- PPA 비교 시 반드시 동일 PVT corner (CORNER, VDD, TEMP) 조건 확인
