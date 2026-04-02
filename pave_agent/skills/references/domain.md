# Domain Skill — 반도체 PPA 해석 규칙

## 셀 타입

| 셀 | 설명 | 특성 |
|----|------|------|
| INV | Inverter | 가장 빠름/작음. 기본 성능 지표 |
| ND2 | 2-input NAND | 중간 |
| NR2 | 2-input NOR | 가장 느림/큼 |

동일 셀 타입 내에서만 PPA 비교가 유의미하다.

## 설계 파라미터 해석

### Drive Strength (DS: D1~D4)
- 트랜지스터 W/L ratio에 의해 결정. 숫자가 클수록 구동력 높음
- D가 N배이면 power/area도 약 N배 증가
- freq_ghz는 DS에 크게 의존하지 않음 (intrinsic delay는 유사)

### VTH 타입 (ULVT, SLVT, LVT, MVT, RVT, HVT)
- low-Vth(ULVT쪽): 고속, 고leakage
- high-Vth(HVT쪽): 저속, 저leakage
- Temperature Inversion은 HVT에서 가장 두드러짐 (저온에서 오히려 느려짐)

### Nanosheet Width (WNS: N1~N5)
- GAA nanosheet 채널 폭. 숫자가 클수록 구동력 높음
- FinFET의 fin 개수 역할을 대체

### Cell Height (CH: CH138, CH148, CH168, CH200)
- Track 수 × metal pitch로 결정
- 줄이면 면적 감소하지만 drive strength 상한 저하 및 라우팅 제약
- CH_TYPE: uHD(ultra-High Density) < HD(High Density) < HP(High Performance)

## 측정 파라미터 해석

### Dynamic 파라미터 (RO 발진 중 측정, 함께 변하는 경향)

| 파라미터 | 단위 | 해석 |
|----------|------|------|
| FREQ_GHZ | GHz | **성능 대표 지표**. f = 1/(2×N×t_pd). 높을수록 좋음. PDK 버전 간 비교의 핵심 |
| D_POWER | mW | 동적 전력. P = C·V²·f. 스위칭 활동 기반 소비 전력 |
| D_ENERGY | | 1회 switching 에너지. D_ENERGY = ACCEFF_FF × V². 동적 에너지 효율 지표 |
| ACCEFF_FF | fF | AC Effective Capacitance. switching에 관여하는 실효 커패시턴스. d_power와 d_energy에 직접 기여 |
| ACREFF_KOHM | kΩ | AC Effective Resistance. 구동 경로의 실효 저항. RC delay → freq_ghz에 직접 영향 |

### Static 파라미터 (입력 고정, 발진 정지 상태에서 측정, 함께 변하는 경향)

| 파라미터 | 단위 | 해석 |
|----------|------|------|
| S_POWER | mW | 정적(누설) 전력. 낮을수록 좋음. 온도에 exponential 의존 (-25°C vs 125°C에서 수십 배 차이) |
| IDDQ_NA | nA | IDDQ 누설전류. 이중 성격: (1) 정상 범위 내 → s_power와 직접 상관하는 leakage 지표, (2) 동일 조건 대비 비정상적으로 높으면 제조 결함 가능성 |

## 공정 코너 해석

| 코너 | NMOS | PMOS | 특성 |
|------|------|------|------|
| TT | Typical | Typical | 기준 동작점 |
| FF | Fast | Fast | 최고 속도(freq↑), 최대 누설(s_power↑, iddq↑) |
| SS | Slow | Slow | 최저 속도(freq↓), 최소 누설(s_power↓, iddq↓) |
| SF | Slow | Fast | NMOS 느림, PMOS 빠름 |
| FS | Fast | Slow | NMOS 빠름, PMOS 느림 |
| SSPG | Slow-Slow Process Guard | worst-case 마진 확인용 |

## PVT 의존성

### 온도 (TEMP)
- s_power/iddq_na는 온도에 exponential 의존 (약 10°C당 1.5~2배 증가)
- freq_ghz: 미세공정에서 **Temperature Inversion** 발생 가능 — 저온에서 오히려 느려짐 (특히 HVT)
- 비교 시 반드시 동일 온도 조건 필요

### 전압 (VDD)
- d_power는 V²에 비례 (10% 증가 시 d_power 약 21% 증가)
- freq_ghz와 양의 상관 (비선형)
- s_power/iddq_na는 DIBL 효과로 exponential 증가

## 트렌드 해석 규칙

- **PDK 버전 간 freq 증가**: SPICE 모델 또는 공정 최적화 결과. s_power 변화도 함께 확인 필요
- **PDK 버전 간 s_power 증가**: 누설 제어 악화 가능. freq 대비 trade-off 검토
- **코너 간 spread 증가**: 공정 변동성 증가 의미. 수율 영향 검토 필요
- **EVT0 → EVT1**: 마스크 개선. 일반적으로 성능/누설 모두 개선 기대

## PPA 트레이드오프 규칙

- **Performance ↔ Power**: freq 증가(속도↑)는 대부분 d_power, s_power 증가를 수반
- **Performance ↔ Area**: Cell Height 축소는 면적 감소하지만 drive strength 상한 저하
- **VTH 선택**: ULVT(최고속/최고누설) ~ HVT(최저속/최저누설). 설계 목적에 따라 선택
- **DS 선택**: D1(최소면적/최소전력) ~ D4(최대구동력/최대전력). 팬아웃에 따라 선택

## 해석 응답 가이드

1. **수치 제시**: 핵심 수치를 먼저 요약한다.
2. **비교 맥락**: 타겟 대비, PDK 버전 대비, 코너 간 비교 맥락을 제공한다.
3. **의미 해석**: 수치가 설계에 미치는 영향을 설명한다.
4. **권장 사항**: 추가 확인이 필요한 사항이 있으면 제안한다.
