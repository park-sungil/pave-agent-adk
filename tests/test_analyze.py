"""Tests for analyze tool and sandbox executor."""

from pave_lib.sandbox.executor import execute


class TestSandboxExecutor:
    def test_basic_execution(self, sample_ppa_data):
        code = """
df = pd.DataFrame(data)
result = {"count": len(df), "columns": list(df.columns)}
"""
        output = execute(code, sample_ppa_data)
        assert "error" not in output
        assert output["result"]["count"] == len(sample_ppa_data)

    def test_statistical_analysis(self, sample_ppa_data):
        code = """
df = pd.DataFrame(data)
vth = df[df['PARAM_NAME'] == 'VTH']['PARAM_VALUE']
result = {
    "mean": float(vth.mean()),
    "std": float(vth.std()),
    "count": int(len(vth)),
}
"""
        output = execute(code, sample_ppa_data)
        assert "error" not in output
        assert "mean" in output["result"]
        assert output["result"]["count"] == 3

    def test_chart_generation(self, sample_ppa_data):
        code = """
df = pd.DataFrame(data)
fig, ax = plt.subplots()
ax.bar(['a', 'b'], [1, 2])
buf = BytesIO()
fig.savefig(buf, format='png')
buf.seek(0)
charts.append(base64.b64encode(buf.read()).decode('utf-8'))
plt.close(fig)
result = {"chart_count": len(charts)}
"""
        output = execute(code, sample_ppa_data)
        assert "error" not in output
        assert len(output["charts"]) == 1
        assert output["result"]["chart_count"] == 1

    def test_error_handling(self, sample_ppa_data):
        code = "x = 1 / 0"
        output = execute(code, sample_ppa_data)
        assert "error" in output

    def test_empty_data(self):
        code = """
df = pd.DataFrame(data)
result = {"empty": len(df) == 0}
"""
        output = execute(code, [])
        assert "error" not in output
        assert output["result"]["empty"] is True
