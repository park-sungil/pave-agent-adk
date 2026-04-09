# 반도체 PPA 도메인 지식

> pave-agent 프롬프트에 삽입하여 LLM이 PPA 데이터 분석 시 참조하도록 한다.
>
> 본 문서의 도메인 지식은 반도체 업계 3대 학회(IEDM, ISSCC, VLSI Symposium) 및 IEEE 저널 논문, 주요 파운드리(TSMC, Samsung, Intel) 발표 자료, IMEC 등 연구기관 논문을 기반으로 검증되었다.

---

## 0. 컬럼명 매핑

본 문서는 반도체 업계 용어를 사용하지만, pave DB의 실제 컬럼명은 다음과 같이 약어/대문자로 저장되어 있다. 해석 시 자연어 용어와 DB 컬럼을 연결할 때 참조할 것.

### 측정 파라미터 (대소문자만 다름)

| 문서 본문 개념 | DB 컬럼 |
|-------------|--------|
| freq_ghz | FREQ_GHZ |
| d_power | D_POWER |
| d_energy | D_ENERGY |
| acceff_ff (Ceff) | ACCEFF_FF |
| acreff_kohm (Reff) | ACREFF_KOHM |
| s_power | S_POWER |
| iddq_na | IDDQ_NA |

### 설계 파라미터 및 측정 조건

| 문서 본문 개념 | DB 컬럼 |
|-------------|--------|
| drive_strength | DS |
| nanosheet_width | WNS |
| cell_height | CH |
| cell height 타입 (HP/HD/uHD) | CH_TYPE |
| vth (threshold voltage) | VTH |
| cell type (INV, ND2, NR2) | CELL |
| process_corner | CORNER |
| temperature | TEMP |
| vdd (supply voltage) | VDD |
| vdd type (UUD/SUD/UD/NM/OD/SOD) | VDD_TYPE |

---

## 1. 파라미터 정의 및 분류

### 1.1 측정 파라미터

| 파라미터 | 분류 | 측정 상태 | 설명 |
|----------|------|-----------|------|
| `FREQ_GHZ` | Performance | Dynamic (RO 발진) | Ring Oscillator 발진 주파수(GHz)로부터 산출. 셀의 intrinsic delay를 반영하는 성능 지표 |
| `D_POWER` | Power (dynamic) | Dynamic (RO 발진) | 스위칭 활동 기반 소비 전력. P ∝ C·V²·f. RO 발진 중 측정 |
| `D_ENERGY` | Energy (dynamic) | Dynamic (RO 발진) | 1회 switching transition당 소비 에너지. D_ENERGY = ACCEFF × V². 동적 에너지 효율의 직접 지표 |
| `ACCEFF_FF` | Capacitance (effective) | Dynamic (RO 발진) | AC Effective Capacitance(fF). RO 발진 시 switching에 관여하는 실효 커패시턴스. 채널(Cgc), overlap(Cov), junction(Cj), wire(Cwire) 커패시턴스의 합. d_power와 d_energy에 직접 기여 |
| `ACREFF_KOHM` | Resistance (effective) | Dynamic (RO 발진) | AC Effective Resistance(kΩ). RO 발진 시 구동 경로의 실효 저항. RC delay를 통해 freq_ghz에 직접 영향 |
| `S_POWER` | Power (static/leakage) | Static (입력 고정) | 트랜지스터 off-state 누설전류 기반 전력. 모든 입력을 고정하고 switching이 멈춘 정적 상태에서 측정 |
| `IDDQ_NA` | Power (static) + 품질/신뢰성 | Static (입력 고정) | IDDQ 누설전류(nA). 대기상태(Quiescent state)에서의 공급전류(IDD)를 측정. 이중 성격을 가진다: (1) 정상 범위 내의 값은 leakage 수준 즉 s_power와 직접 상관하는 전력 특성 지표, (2) 비정상적으로 높은 값은 제조 결함을 의미하는 품질 지표 |

### 1.2 설계 파라미터

| 파라미터 | 설명 |
|----------|------|
| `drive_strength` | 셀의 출력 전류 구동 능력. 트랜지스터 W/L ratio에 의해 결정. D1, D2, D3, ... 과 같이 표기하며 숫자가 클수록 구동력이 높다 |
| `nanosheet_width` | GAA(Gate-All-Around) nanosheet FET에서 채널 시트의 가로 폭. nm 수치로 표현하거나 N1, N2, N3, ... 과 같이 단계별로 표기한다. 숫자가 클수록 폭이 넓다. FinFET의 fin 개수 역할을 대체하며 연속적 조절이 가능하다 |
| `cell_height` | Standard cell의 고정 세로 높이. 실무에서는 CH + 물리적 높이(nm) 형태로 표기한다 (예: CH138 = 138nm, CH168 = 168nm, CH200 = 200nm). Track 수 × metal pitch(nm)로 산출되며, CH 값이 클수록 내부에 더 큰 트랜지스터와 라우팅 자원을 확보할 수 있다 |
| `vth` | Threshold Voltage. 트랜지스터 on/off 전환 최소 게이트 전압. ULVT/SLVT/VLVT/LVT/MVT/RVT/HVT 등 multi-Vth 옵션으로 제공되며, 왼쪽일수록 low-Vth(고속, 고leakage), 오른쪽일수록 high-Vth(저속, 저leakage) |

### 1.3 측정 조건

| 조건 | 설명 |
|------|------|
| `temperature` | 측정 온도 조건. 동일 칩이라도 온도에 따라 power, performance 값이 크게 달라진다 |
| `vdd` | 공급 전압. PPA 세 축 모두에 직접 영향을 미치는 핵심 조건이다 |
| `process_corner` | 공정 편차 조건. FF(Fast-Fast), TT(Typical-Typical), SS(Slow-Slow) 등으로 표기한다. pave 시스템에서는 주로 TT와 SSPG가 사용된다 |

pave 시스템의 주요 process corner:
- **TT** (Typical-Typical): NMOS/PMOS 모두 typical한 조건. 기본 조회 및 비교의 기준 corner.
- **SSPG** (SS + Performance + Global): SS(Slow-Slow) 디바이스 모델에 Global Variation(chip-mean, 칩 단위로 나타나는 공정 편차)을 반영한 performance corner. 순수 SS보다 현실적인 worst-case이며, 성능 마진 확인에 사용된다.

---

## 2. PDK (Process Design Kit)

### 2.1 정의

PDK는 파운드리가 설계자에게 제공하는 특정 공정 노드의 설계 도구 모음이다. 해당 공정에서 칩을 설계하는 데 필요한 물리적 특성, 규칙, 모델을 패키지로 포함한다. 섹션 1에서 정의한 모든 파라미터와 측정 조건은 PDK를 기반으로 생성된다.

### 2.2 PDK 구성 요소와 PPA 연관

| 구성 요소 | 내용 | PPA 영향 |
|-----------|------|----------|
| Design Rule | 최소 metal width, spacing, via size 등 레이아웃 규칙 | Area에 직접 영향. rule 변경 시 셀 면적 변동 |
| SPICE Model | 트랜지스터 전기적 특성 모델. PVT corner별로 제공 | Performance, Power 시뮬레이션의 근거. 모델 업데이트 시 delay, power 예측값 변동 |
| Technology File | EDA 툴용 공정 정보. layer 정의, 기생 RC 파라미터, interconnect 모델 | wire delay, parasitic power에 영향 |
| Standard Cell Library | INV, ND2, NR2 등 기본 셀. Liberty(.lib) 파일에 PVT corner별 timing, power, area 정보 포함 | PPA 데이터의 직접적 출처. drive strength 변종(D1, D2, D3, ...)과 multi-Vth 변종(ULVT~HVT)이 모두 포함 |

### 2.3 PDK 버전과 PPA 데이터

- PDK 버전이 바뀌면 동일 설계라도 PPA 결과가 달라진다.
- SPICE 모델 업데이트 → timing/power 시뮬레이션 결과 변동.
- Design rule 변경 → 셀 면적, 라우팅 가능성 변동.
- Cell library 업데이트 → 셀별 timing/power 특성 변동.
- PDK 버전은 PVT corner와 함께 PPA 데이터 비교의 필수 조건이다.

---

## 3. PPA 기본 Trade-off

- **Performance ↔ Power**: freq_ghz를 높이면 d_power가 증가한다. voltage를 올리면 power는 V²에 비례하여 급증한다.
- **Performance ↔ Area**: 성능 향상(wider logic, bigger cache)은 die area 증가를 수반한다.
- **Power ↔ Area**: 트랜지스터 수 증가 → S_POWER(leakage) 증가. 공정 미세화 시 leakage 밀도도 증가할 수 있다.

---

## 4. 기본 셀 타입

### 4.1 INV (Inverter)

- 구성: PMOS 1개 + NMOS 1개. 입력 신호를 반전.
- 라이브러리에서 가장 작은 면적의 셀.
- FO4 delay(fanout-of-4 inverter delay)가 공정 노드 간 성능 비교의 표준 메트릭으로 사용된다.
- PPA 측정의 기준점(reference cell).

### 4.2 ND2 (2-input NAND)

- 구성: PMOS 2개 병렬 + NMOS 2개 직렬.
- NMOS 직렬로 인해 pull-down 저항이 INV보다 높아 동일 drive strength에서 INV보다 느리고 면적이 크다.
- Universal gate로서 모든 논리 함수 구현 가능. 디지털 설계에서 가장 빈번하게 사용되는 셀 중 하나.

### 4.3 NR2 (2-input NOR)

- 구성: PMOS 2개 직렬 + NMOS 2개 병렬.
- PMOS 직렬 + PMOS의 낮은 mobility로 인해 pull-up이 NAND의 pull-down보다 느리다.
- 동일 성능을 내려면 PMOS를 더 크게 설계해야 하므로 면적이 ND2보다 크다.
- CMOS 설계에서는 ND2가 NR2보다 면적·속도 면에서 유리하여 NAND 기반 설계가 선호된다.

### 4.4 셀 타입 간 PPA 순서 (동일 입력 수, 동일 drive strength 기준)

| 지표 | 순서 (우수 → 열위) |
|------|---------------------|
| Performance (speed) | INV > ND2 > NR2 |
| Power (낮을수록 우수) | INV < ND2 < NR2 |
| Area (작을수록 우수) | INV < ND2 < NR2 |

### 4.5 Ring Oscillator (RO)

#### 구조와 동작 원리

Ring Oscillator는 홀수 개의 inverter(또는 다른 반전 셀)를 직렬 연결하고 마지막 출력을 첫 번째 입력으로 피드백시킨 구조이다. 별도의 클럭 없이 자체 발진하며, 발진 주파수는 f = 1 / (2 × N × t_pd)로 결정된다 (N = 셀 수, t_pd = 셀당 propagation delay).

#### PPA 측정에서의 역할

단일 셀의 delay는 picosecond 단위로 직접 측정이 어렵다. RO로 수십~수백 개 셀을 연결하면 발진 주파수를 쉽게 측정할 수 있고, 역산으로 셀당 delay를 구할 수 있다. 이 때문에 RO frequency는 공정 성능의 대표 지표로 사용된다:
- PDK 버전 간 성능 비교
- PVT corner별 성능 특성 파악
- Vth / Drive Strength / Nanosheet Width / Cell Height 변경에 따른 성능 영향 평가
- 웨이퍼 내/간 공정 균일성(uniformity) 모니터링

#### RO 변종

INV 기반 RO가 기본이지만, ND2, NR2 등 다른 셀로도 RO를 구성하여 셀 타입별 delay를 비교한다. 또한 같은 셀 타입이라도 drive strength(D1, D2, ...), Vth(ULVT~HVT), cell height(CH138, CH168, ...), nanosheet width(N1, N2, ...) 조합별로 RO를 만들어 PPA를 체계적으로 평가한다.

#### RO와 측정 파라미터의 관계

| 측정 상태 | 파라미터 | 설명 |
|-----------|----------|------|
| Dynamic (RO 발진 중) | FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, ACREFF_KOHM | RO가 발진하는 switching 상태에서 측정. 셀의 속도, 동적 전력, 에너지, 실효 RC 특성을 반영 |
| Static (입력 고정, 발진 정지) | S_POWER, IDDQ_NA | 모든 입력을 고정하고 switching이 완전히 멈춘 정적 상태에서 측정. 셀의 누설전류와 품질을 반영 |

#### Dynamic 측정 파라미터 간 핵심 관계

ACCEFF_FF(Ceff)와 ACREFF_KOHM(Reff)는 RO 특성의 근본 파라미터이며, 다른 Dynamic 측정값의 기반이 된다:

- **Delay ∝ Reff × Ceff**: 셀당 propagation delay는 실효 저항과 실효 커패시턴스의 곱에 비례한다. 따라서 FREQ_GHZ ∝ 1 / (Reff × Ceff). 이 관계는 14nm FinFET RO에서 Ceff의 정량적 모델로 검증되었다 (IEEE, 2018).
- **D_ENERGY = Ceff × VDD²**: 1회 switching당 소비 에너지는 실효 커패시턴스와 전압 제곱에 비례한다.
- **D_POWER = D_ENERGY × freq = Ceff × VDD² × freq**: 동적 전력은 에너지와 주파수의 곱이다.

이 관계에서 Ceff가 줄면 delay 감소(성능↑) + energy 감소(전력↑)로 양쪽 모두 개선되므로, Ceff 저감은 PPA 최적화의 핵심이다. Reff가 줄면 delay 감소(성능↑)이지만 energy에는 직접 영향하지 않는다.

16nm FinFET RO 공정 최적화 연구(Su & Li, IEEE)에서는 gate spacer 두께, S/D proximity, S/D depth, S/D implant가 Ceff, Reff, IDDQ 세 파라미터에 동시에 영향을 미치며, 이 중 gate spacer 두께가 가장 지배적인 변동 요인으로 보고되었다.

이 구분은 데이터 해석에서 중요하다: FREQ_GHZ, D_POWER, D_ENERGY, ACCEFF_FF, acreff_kohm은 모두 Dynamic 측정으로 함께 변하는 경향이 있고, s_power와 iddq_na도 Static 측정으로 함께 변하는 경향이 있다. 그러나 Dynamic 지표와 Static 지표 간에는 반드시 같은 방향으로 변하지 않을 수 있다.

---

## 5. 설계 파라미터별 PPA 영향

### 5.1 Drive Strength

| PPA 축 | 영향 |
|--------|------|
| Performance | 높을수록 출력 transition 가속. fanout이 크거나 wire가 긴 경우 timing 유리 |
| Power | D_POWER: switching capacitance 증가. S_POWER: leakage area 증가. D4는 D1 대비 약 4배 전력 |
| Area | 트랜지스터 크기에 비례하여 셀 면적 증가. D2 ≈ D1의 약 2배 |

- EDA 툴은 timing slack이 충분한 경로에 low drive strength, 빡빡한 경로에 high drive strength를 배치하여 PPA를 최적화한다.
- 실효 구동 능력은 VDD와 온도에 따라 변한다. VDD가 낮거나, temperature inversion이 있는 공정의 저온 조건에서는 drive capability가 저하될 수 있다.
- Ceff/Reff 관점: drive strength가 높아지면(D1→D4) 트랜지스터 폭 증가로 Reff는 감소(구동력↑)하지만 Ceff는 증가(부하↑)한다. delay = Reff × Ceff에서 Reff 감소 효과가 Ceff 증가를 상쇄하므로 성능이 향상되나, D_ENERGY = Ceff × VDD²는 증가한다.

### 5.2 Nanosheet Width

| PPA 축 | 영향 |
|--------|------|
| Performance | 넓을수록 채널 면적 증가 → 전류 구동력 향상 → FREQ_GHZ 유리 |
| Power | D_POWER: capacitance 증가. S_POWER: 채널 면적 증가로 leakage 증가 |
| Area | 같은 셀 footprint 내에서 조절 가능하여 FinFET(fin 개수)보다 면적 효율이 높음. 과도하게 키우면 셀 폭 증가 |

- GAA 시대에서 drive strength 조절의 핵심 메커니즘이다. FinFET의 fin 개수 역할을 대체한다.
- Mixed-width 설계: 같은 칩 내에서 critical path에는 wide, non-critical path에는 narrow nanosheet을 사용하여 PPA를 최적화한다. TSMC는 IEDM 2024에서 N2(2nm) 기술의 "NanoFlex"로 이를 구현했으며, Samsung은 IEDM 2018에서 3nm GAA MBCFET의 nanosheet width 조절을 통한 PPA 최적화를 발표하였다.
- Ceff/Reff 관점: nanosheet width가 넓어지면 채널 면적 증가로 Reff 감소(구동력↑) + Ceff 증가(게이트 커패시턴스↑). drive strength 증가와 유사한 trade-off이며, 에너지(D_ENERGY)는 Ceff에 비례하여 증가한다.

### 5.3 Cell Height

| PPA 축 | 영향 |
|--------|------|
| Performance | 줄이면 트랜지스터 크기 및 라우팅 트랙 제한 → drive strength 상한 저하, 라우팅 detour에 의한 wire delay 증가 가능 |
| Power | 면적 감소로 capacitance 감소(D_POWER 유리), 라우팅 혼잡 시 wire length 증가로 power 증가 가능 |
| Area | 줄이면 셀 면적이 직접 감소. 공정 미세화에서 area scaling의 핵심 레버 |

- Track 수가 많을수록(예: 7T > 6T > 5T) 내부에 큰 트랜지스터와 많은 라우팅 자원을 확보할 수 있어 성능이 높지만 면적이 커진다.
- Cell height의 물리적 크기(nm)는 track 수 × metal pitch로 결정되며, 실무에서는 CH + nm 값으로 표기한다 (예: CH138, CH168, CH200).
- CH 값과 track 수의 관계: 동일 track 수라도 metal pitch가 다르면 CH 값이 달라지고, 동일 CH 값이라도 metal pitch에 따라 track 수가 달라진다. CH 값은 물리적 높이를 직접 나타내므로, area 계산에서 track 수보다 직관적이다.
- 공정 노드별 대표 사례:
  - 7nm: 6~6.5T cell, M2 pitch 36nm → CH216~CH240 수준
  - 5nm: 6T cell, M2 pitch 28~30nm → CH168~CH180 수준
  - 3nm/4nm: 5~5.5T cell, M2 pitch 21~24nm → CH105~CH132 수준
  - 2nm: 5T cell, M2 pitch 16~20nm → CH80~CH100 수준 (IMEC/TSMC IEDM 발표 기준)
- 미세공정에서는 pitch scaling 둔화로 cell height reduction이 area scaling의 주요 수단이 되고 있다.
- cell height × nanosheet width × sheet 적층 수가 함께 해당 셀의 최대 구동 능력을 결정한다.

### 5.4 Vth (Threshold Voltage)

| Vth 종류 | 특성 |
|----------|------|
| ULVT (Ultra-Low) | 극고속, 극고 leakage. 최소한의 critical path에만 사용 |
| SLVT (Super-Low) | ULVT보다 약간 완화. 여전히 매우 높은 leakage |
| VLVT (Very-Low) | 고속, 고 leakage. 성능 요구가 높은 경로에 사용 |
| LVT (Low) | 고속, 높은 leakage. critical path의 주력 |
| MVT (Medium) | 속도-leakage 중간. general logic에 활용 |
| RVT (Regular) | 속도-leakage 균형형. 면적 대비 효율 우수 |
| HVT (High) | 저속, 극저 leakage. non-critical path 및 저전력 설계에 사용 |

| PPA 축 | 영향 |
|--------|------|
| Performance | Vth가 낮을수록 gate overdrive(VDD - Vth) 증가 → switching speed 향상. critical path에 ULVT~LVT 배치 |
| Power (S_POWER) | Vth가 낮을수록 sub-threshold leakage가 exponential 증가. 이론적으로 subthreshold slope(~60mV/decade) 기준 Vth 60mV 감소 시 leakage 10배 증가. FinFET/GAA에서는 subthreshold slope이 개선되어 실제 비율은 이보다 완만할 수 있으나, ULVT는 HVT 대비 수백 배 이상 leakage 차이가 날 수 있다. 업계 경험에 따르면 HVT 사용 시 LVT 대비 leakage를 최대 80% 줄일 수 있으나 timing에 약 20% 영향 |
| Power (D_POWER) | low-Vth(ULVT~LVT)가 약간 높은 편이나, 빠른 transition으로 short-circuit current 감소 효과도 있어 복합적 |
| Area | 직접 영향 없으나, high-Vth(RVT~HVT)는 느리므로 timing 확보를 위해 높은 drive strength 필요 → 면적 증가 가능. low-Vth(ULVT~LVT)는 작은 셀로도 timing 충족 가능 |

- Vth는 온도와 VDD에 따라 변한다. 고온에서 Vth 하락 → leakage 심화 (S_POWER 온도 의존성의 근본 원인). VDD 상승 → DIBL로 실효 Vth 하락 → leakage 증가.
- Temperature Inversion은 Vth의 온도 의존성에서 비롯된다. 저온에서 Vth 상승이 mobility 개선을 압도하는 현상. high-Vth(RVT~HVT) 셀에서 가장 두드러지고, low-Vth(ULVT~LVT) 셀에서는 거의 나타나지 않는다.
- 근거: Intel 22nm FinFET IEDM 2012에서 multi-Vth(HP/SP/LP) IV 곡선이 공개되었으며, IEDM 2018에서 IBM이 7nm 공정의 multi-Vt 기법(work function 기반)을 발표하였다.

---

## 6. 조건별 상관관계

### 6.1 Temperature × PPA

#### S_POWER — 온도 의존성 매우 높음 (exponential)
- 누설전류는 온도에 exponential하게 증가한다. 이는 sub-threshold leakage 수식에서 Vth가 온도에 따라 선형 감소하고, leakage가 exp(-Vth/nkT)에 비례하기 때문이다 (Roy et al., Proc. IEEE, 2003).
- 약 10°C 상승 시 leakage가 대략 1.5~2배 증가하는 것으로 알려져 있으나, 실제 비율은 공정 노드, Vth, 온도 구간에 따라 달라진다.
- 동일 칩이라도 -25°C vs 125°C에서 s_power가 수십 배 차이날 수 있다.
- FinFET에서는 이 온도-leakage positive feedback이 thermal runaway를 유발할 수 있다. Thermal runaway란 leakage 증가 → 발열 → 온도 상승 → leakage 추가 증가의 악순환이 제어 불가능한 수준에 도달하는 현상으로, 칩 손상으로 이어질 수 있다 (IEEE 연구에서 28nm FinFET 대상 보고).

#### D_POWER — 온도 의존성 낮음 (약한 양의 상관)
- 온도 상승 → carrier mobility 감소 → transition time 증가 → short-circuit current 미세 증가.
- S_POWER 대비 민감도가 훨씬 낮아 일반적 비교에서는 무시 가능.

#### IDDQ_NA — s_power와 동일한 exponential 온도 의존성
- leakage 기반 지표이므로 s_power와 같은 온도 의존성을 가진다.
- IDDQ 기반 불량 판정 시 반드시 동일 온도 조건의 threshold을 적용해야 한다.

#### FREQ_GHZ — Temperature Inversion 주의
- 전통적 이해 (구형 공정, >65nm): 고온 → carrier mobility 감소 → 속도 저하. worst-case performance = high temperature.
- 미세공정 (65nm 이하): Temperature Inversion 발생. 저온에서 Vth 상승 효과가 mobility 개선을 압도하여, 오히려 저온에서 freq_ghz가 낮아지는 역전 현상. 45nm에서 VDD=0.8V 조건으로 관측되었으며, 7nm 이하에서는 거의 항상 발생.
- Vth 종류에 따라 민감도가 다르다: HVT/RVT 셀은 temperature inversion 효과가 가장 크고, MVT/LVT는 중간, VLVT/SLVT/ULVT는 거의 영향을 받지 않는다. 이는 gate overdrive(VDD - Vth) 크기 차이에 기인한다.
- freq_ghz의 worst-case corner가 high temp인지 low temp인지는 공정 노드와 Vth 종류에 따라 다르다. "고온 = worst performance"로 단순 가정하지 않는다.
- 근거: IEDM/VLSI 학회 발표 및 다수의 IEEE 논문에서 sub-65nm 공정의 temperature inversion이 보고됨.

#### ACCEFF_FF / ACREFF_KOHM — 온도에 따른 변화
- ACREFF_KOHM(Reff): 온도 상승 시 carrier mobility 감소로 Reff가 증가한다. 이는 FREQ_GHZ 저하의 직접 원인이다 (temperature inversion이 없는 경우).
- ACCEFF_FF(Ceff): 온도에 대한 직접 의존성은 Reff보다 약하다. 다만 junction capacitance가 온도에 따라 미세하게 변하고, Vth 변화로 인한 inversion charge 변동이 채널 커패시턴스에 영향을 줄 수 있다.
- D_ENERGY: Ceff가 온도에 비교적 안정적이므로 D_ENERGY = Ceff × VDD²도 온도에 큰 변화를 보이지 않는다. 온도에 따른 전력 변화는 주로 S_POWER(leakage)가 지배한다.

### 6.2 VDD × PPA

#### D_POWER — V² 비례 (가장 직접적)
- P_dynamic = C · V² · f 에서 VDD가 제곱으로 기여한다.
- VDD 10% 증가 시 D_POWER 약 21% 증가. 전력 절감의 가장 효과적인 수단이 VDD 저감이다.

#### S_POWER — exponential 관계
- VDD 상승 → DIBL(Drain-Induced Barrier Lowering) 효과로 실효 Vth 감소 → sub-threshold leakage exponential 증가.
- Gate leakage도 oxide 양단 전압 증가로 커진다.

#### IDDQ_NA — s_power와 동일 방향
- VDD가 올라가면 leakage 증가로 iddq도 함께 상승한다.

#### FREQ_GHZ — 양의 상관 (비선형)
- VDD 상승 → gate overdrive (VDD - Vth) 증가 → switching speed 향상.
- VDD가 Vth에 근접할수록 성능이 급격히 저하되는 비선형 특성을 가진다.

#### Area — 간접 영향
- VDD 자체가 면적을 변경하지 않으나, 낮은 VDD에서 noise margin 확보를 위해 트랜지스터/회로 추가가 필요할 수 있다.

#### ACCEFF_FF / ACREFF_KOHM — VDD에 따른 변화
- ACREFF_KOHM(Reff): VDD 상승 시 gate overdrive 증가로 채널 저항이 감소하여 Reff가 낮아진다. 이것이 FREQ_GHZ 향상의 직접 메커니즘이다. CFET vs nanosheet 비교 연구(IEEE JEDS)에서 Ceff, Reff vs VDD 특성이 보고되었다.
- ACCEFF_FF(Ceff): VDD에 대해 약한 의존성을 가진다. VDD가 높아지면 inversion charge 증가로 채널 커패시턴스가 약간 증가하지만, Reff 변화에 비해 작은 편이다.
- D_ENERGY = Ceff × VDD²: Ceff가 비교적 안정적이므로, d_energy는 주로 VDD²에 의해 결정된다. VDD를 10% 낮추면 d_energy가 약 19% 감소하여 에너지 효율 개선의 가장 효과적인 수단이다.

### 6.3 PVT Corner 조합의 Worst-case 매핑

| 분석 목적 | Worst-case Corner |
|-----------|-------------------|
| 최대 전력 소비 (D_POWER) | High Temp, Slow Process, High Voltage |
| 최저 성능 (FREQ_GHZ) | SSPG corner 기준. Temperature Inversion 여부에 따라 worst-case 온도가 달라짐 (섹션 6.1 참조) |
| Leakage 상한 (S_POWER/IDDQ_NA) | High Temp, High Voltage |
| IDDQ 불량 판정 | 측정 온도·VDD 조건의 threshold 기준 적용 |

pave 시스템에서 성능 worst-case 분석 시 SSPG corner를 기본으로 사용한다.

---

## 7. IDDQ 테스팅 방법론

### 7.1 원리

IDDQ(IDD Quiescent) 테스팅은 대기상태(Quiescent state)에서의 공급전류(IDD)를 측정하여 제조 결함을 검출하는 회로 테스팅 방법론이다.

정상 CMOS 회로의 기본 특성: 신호 전환(switching) 시에는 순간적으로 전류가 흐르지만, 전환이 완료되고 과도 현상이 사라진 정적 상태에서는 이상적으로 전류가 0에 가까워야 한다. 정상 칩의 quiescent current는 수 nA 수준이다.

결함이 있는 경우: gate-oxide short, metal line 간 bridging, transistor stuck-on 등 공정 결함이 있으면 VDD에서 GND로의 비정상적 전도 경로가 형성되어, 정적 상태에서도 정상 대비 3~5 자릿수(orders of magnitude) 높은 전류가 흐른다.

### 7.2 결함과 기능의 관계

- 결함이 있어도 특정 입력 조건에서는 기능이 정상 동작할 수 있다. 예를 들어, 특정 신호선이 VDD에 short되어 있더라도 해당 선을 '1'로 구동하는 입력에서는 추가 전류가 흐르지 않는다.
- 그러나 다른 입력 조건에서는 비정상 전류가 발생하며, 전력 소비가 증가한다.
- 전력 소비가 과도하게 커지면 전압 강하(IR drop)나 발열로 인해 기능 오류로 이어질 수 있다.
- 따라서 IDDQ 테스팅은 기능 테스트(functional test)를 대체하는 것이 아니라, 기능 테스트가 놓칠 수 있는 결함을 보완적으로 검출하는 수단이다.

### 7.3 검출 가능 결함 유형

- Bridging fault (신호선 간 단락)
- Gate-oxide short (게이트 산화막 결함)
- Transistor stuck-on fault
- Line/drain/source break fault (단선으로 인한 floating node)

### 7.4 미세공정에서의 한계

공정이 미세화되면서 정상 트랜지스터의 leakage current 자체가 높아지고, 칩 내 트랜지스터 수가 증가하여 총 background leakage가 커진다. 이로 인해 결함에 의한 비정상 전류와 자연적 leakage를 구별하기 어려워지는 한계가 있다. 이를 극복하기 위해 power gating(블록별 전원 차단)을 통한 개별 블록 테스트, background current 보상 기법 등이 사용된다.

### 7.5 pave-agent에서의 IDDQ_NA 해석 지침

- iddq_na는 이중 성격을 가진다. 맥락에 따라 해석 방식을 구분한다:
  - **전력 특성 관점**: 정상 범위 내의 IDDQ_NA 값은 해당 칩의 leakage 수준을 반영하며 s_power와 직접 상관한다. "power가 높은 칩", "leakage 비교" 등의 쿼리에서는 iddq_na를 s_power와 함께 전력 지표로 활용할 수 있다.
  - **설계 주의 관점 (v8)**: 두 PDK 간 비교에서 동일 조건 대비 IDDQ_NA 변화율이 비정상적으로 큰 경우, 해당 파라미터 영역에서 설계 시 마진 확보가 필요함을 의미한다. 이는 제조 결함이 아니라 모델링이 정상인 상태에서 나타나는 특성이다.
  - **품질/결함 관점**: 동일 PDK 내에서 통계적으로 비정상적으로 높은 iddq_na는 제조 결함(bridging, gate-oxide short 등)을 의미할 수 있다.
- 정상/비정상의 경계 판단은 동일 조건(동일 온도, 동일 VDD, 동일 셀 타입) 내에서의 분포를 기준으로 한다.
- IDDQ 데이터의 온도·VDD 의존성은 s_power와 동일한 방향(exponential)이므로, 비교 시 반드시 동일 측정 조건을 확인한다.
