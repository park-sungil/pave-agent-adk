# Analysis Skill

LLM이 분석 코드를 생성할 때 참고하는 규칙.
생성된 코드는 sandbox에서 실행되며, pd/np/plt/stats/base64/BytesIO가 pre-import 되어 있다.

## Code Generation Conventions

### 입력
- `data` 변수: list of dicts. `df = pd.DataFrame(data)`로 변환 후 사용.
- 여러 PDK 비교 시 `PDK_ID` 컬럼으로 구분.

### 출력
- `result` dict에 수치 결과 저장.
- `charts` list에 base64 PNG 저장.
- import 문을 작성하지 마라 — 이미 되어 있다.

### 차트 생성
```python
fig, ax = plt.subplots(figsize=(10, 6))
# ... plotting ...
buf = BytesIO()
fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
buf.seek(0)
charts.append(base64.b64encode(buf.read()).decode('utf-8'))
plt.close(fig)
```

## PDK Benchmarking (N vs N-1)

두 PDK 간 PPA 비교. 가장 빈번한 분석 유형.

### 핵심 규칙
- 반드시 **동일 PVT 조건**(CORNER, VDD, TEMP)에서 비교해야 한다. 조건이 다르면 비교가 무의미.
- 동일 CELL, DS, VTH, WNS, CH 조건끼리 1:1 매칭 후 delta 계산.

### 패턴: 조건별 delta 분석
```python
df = pd.DataFrame(data)
merge_keys = ['CELL', 'DS', 'CORNER', 'TEMP', 'VDD', 'VTH', 'WNS', 'CH']
metrics = ['FREQ_GHZ', 'D_POWER', 'S_POWER', 'IDDQ_NA']

pdk_a = df[df['PDK_ID'] == pdk_ids[0]]
pdk_b = df[df['PDK_ID'] == pdk_ids[1]]

merged = pdk_a.merge(pdk_b, on=merge_keys, suffixes=('_A', '_B'))

for m in metrics:
    merged[f'{m}_delta'] = merged[f'{m}_B'] - merged[f'{m}_A']
    merged[f'{m}_pct'] = merged[f'{m}_delta'] / merged[f'{m}_A'] * 100
```

### 패턴: 조건 그룹별 요약
```python
# CORNER×VDD×TEMP 조건별 평균 delta
summary = merged.groupby(['CORNER', 'VDD', 'TEMP'])[[f'{m}_pct' for m in metrics]].mean()
```

### 차트: 벤치마킹 비교
- **Grouped bar**: PDK A vs B의 metric별 평균 값 비교
- **Heatmap**: CORNER×VDD 조건별 freq % 변화
- **Scatter**: freq 향상 vs leakage 증가 trade-off

## Data Preprocessing

1. NaN은 분석 전 제거하거나 명시적으로 처리.
2. 동일 파라미터는 동일 단위.
3. 이상치는 IQR로 식별하되, 제거는 명시 요청 시에만.
