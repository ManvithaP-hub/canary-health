import pytest

from canary_health.health import (
    MetricSample,
    Baseline,
    health_index,
    latency_penalty,
    error_penalty,
    budget_burn_penalty,
)

BASELINE = Baseline(p99_latency_ms=100.0, error_rate=0.001)


def test_latency_penalty_zero_at_baseline():
    assert latency_penalty(100.0, 100.0) == 0.0


def test_latency_penalty_zero_below_baseline():
    assert latency_penalty(80.0, 100.0) == 0.0


def test_latency_penalty_increases_with_degradation():
    p1 = latency_penalty(150.0, 100.0)
    p2 = latency_penalty(250.0, 100.0)
    assert 0.0 < p1 < p2 <= 1.0


def test_latency_penalty_clamped_at_one():
    assert latency_penalty(10_000.0, 100.0) == 1.0


def test_error_penalty_zero_below_baseline():
    assert error_penalty(0.0005, 0.001) == 0.0


def test_error_penalty_increases_with_surge():
    p1 = error_penalty(0.01, 0.001)
    p2 = error_penalty(0.05, 0.001)
    assert 0.0 < p1 < p2 <= 1.0


def test_budget_burn_penalty_zero_at_or_below_sustainable_rate():
    assert budget_burn_penalty(1.0) == 0.0
    assert budget_burn_penalty(0.5) == 0.0


def test_budget_burn_penalty_increases_with_velocity():
    p1 = budget_burn_penalty(5.0)
    p2 = budget_burn_penalty(12.0)
    assert 0.0 < p1 < p2 <= 1.0


def test_health_index_perfect_health():
    sample = MetricSample(p99_latency_ms=100.0, error_rate=0.001, budget_burn_rate=1.0)
    assert health_index(sample, BASELINE) == 1.0


def test_health_index_degrades_with_worse_metrics():
    good = MetricSample(p99_latency_ms=100.0, error_rate=0.001, budget_burn_rate=1.0)
    bad = MetricSample(p99_latency_ms=300.0, error_rate=0.05, budget_burn_rate=15.0)
    assert health_index(bad, BASELINE) < health_index(good, BASELINE)


def test_health_index_bounded_zero_to_one():
    extreme = MetricSample(p99_latency_ms=10_000.0, error_rate=1.0, budget_burn_rate=1000.0)
    h = health_index(extreme, BASELINE)
    assert 0.0 <= h <= 1.0


def test_weights_must_sum_to_one():
    sample = MetricSample(p99_latency_ms=100.0, error_rate=0.001, budget_burn_rate=1.0)
    with pytest.raises(ValueError):
        health_index(sample, BASELINE, weights={"latency": 0.5, "error_rate": 0.5, "budget_burn": 0.5})


def test_custom_weights_are_respected():
    # An all-weight-on-latency config should be insensitive to error-rate surges.
    sample = MetricSample(p99_latency_ms=100.0, error_rate=0.09, budget_burn_rate=1.0)
    h = health_index(sample, BASELINE, weights={"latency": 1.0, "error_rate": 0.0, "budget_burn": 0.0})
    assert h == 1.0
