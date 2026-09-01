from measure_map_performance import summarize_durations


def test_measurement_summary_contains_percentiles():
    summary = summarize_durations([0.1, 0.2, 0.3, 0.4])

    assert summary["count"] == 4
    assert summary["p50_ms"] > 0
    assert summary["p95_ms"] >= summary["p50_ms"]
