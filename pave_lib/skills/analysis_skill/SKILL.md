---
name: analysis_skill
description: PPA 데이터 분석을 위한 코드 생성 패턴, 컨벤션, 데이터 전처리 규칙을 정의한다. analyze tool이 Python 코드를 생성할 때 참조한다.
---

# Analysis Skill

## Code Generation Conventions

### 필수 임포트
```python
import pandas as pd
import numpy as np
from scipy import stats
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
```

### 입력 데이터 형식
- 데이터는 `data` 변수로 전달된다 (list of dicts).
- `df = pd.DataFrame(data)` 로 DataFrame 변환 후 분석한다.

### 출력 형식
- 수치 결과는 `result` dict에 저장한다.
- 차트는 `charts` list에 base64 PNG로 저장한다.
- 최종 출력: `{"result": result, "charts": charts}`

### 차트 생성 규칙
```python
import base64
from io import BytesIO

fig, ax = plt.subplots(figsize=(10, 6))
# ... plotting code ...
buf = BytesIO()
fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
buf.seek(0)
chart_b64 = base64.b64encode(buf.read()).decode('utf-8')
plt.close(fig)
charts.append(chart_b64)
```

## Analysis Patterns

### 기본 통계
- 평균, 중앙값, 표준편차, 최소/최대
- `df.describe()` 활용

### 상관 분석
- Pearson 상관계수: `stats.pearsonr(x, y)`
- 산점도 + 회귀선 시각화

### 트렌드 분석
- 시계열 데이터의 추세 파악
- 선형 회귀: `stats.linregress(x, y)`
- 시계열 플롯 + 추세선

### 분포 분석
- 히스토그램 + KDE
- 정규성 검정: `stats.shapiro(data)`

### 코너별 비교
- 공정 코너(TT, FF, SS, SF, FS)별 파라미터 비교
- Box plot 또는 violin plot

### 셀 간 비교
- 동일 파라미터에 대해 여러 셀 비교
- Grouped bar chart

## Data Preprocessing Rules

1. **결측치**: NaN은 분석 전에 제거하거나 명시적으로 처리한다.
2. **단위 통일**: 동일 파라미터는 동일 단위로 변환 후 분석한다.
3. **이상치**: IQR 방법으로 이상치를 식별하되, 제거는 명시적 요청이 있을 때만 수행한다.
4. **코너 필터링**: 특정 코너 분석 시 명시적으로 필터링한다. 기본은 전체 코너.
