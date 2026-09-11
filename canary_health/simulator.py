"""Synthetic metric-stream generators used to quantitatively exercise the
controller against the scenario types discussed qualitatively in the
paper: a healthy rollout, a latency-degradation regression, an error-rate
spike, and error-budget exhaustion. A fifth scenario, `noisy_transient`,
injects a single-step glitch to validate the smoothing/debounce logic
against unnecessary rollbacks (paper Section 5, "Metric Granularity and
Noise").

All series are deterministic for a given seed, so results are
reproducible across runs and machines.
"""
import random
from typing import List

from .health import MetricSample, Baseline, health_index

BASELINE = Baseline(p99_latency_ms=120.0, error_rate=0.002)


def _sample_series(n: int, latency_fn, error_fn, burn_fn, seed: int) -> List[MetricSample]:
    rng = random.Random(seed)
    samples = []
    for t in range(n):
        samples.append(
            MetricSample(
                p99_latency_ms=latency_fn(t, rng),
                error_rate=error_fn(t, rng),
                budget_burn_rate=burn_fn(t, rng),
            )
        )
    return samples


def scenario_healthy(n: int = 20, seed: int = 42) -> List[MetricSample]:
    """Canary tracks the stable baseline within normal noise for the whole window."""
    return _sample_series(
        n,
        lambda t, r: BASELINE.p99_latency_ms * (1.0 + r.uniform(-0.05, 0.05)),
        lambda t, r: max(0.0, BASELINE.error_rate + r.uniform(-0.001, 0.001)),
        lambda t, r: 1.0 + r.uniform(-0.2, 0.2),
        seed,
    )


def scenario_latency_degradation(n: int = 20, seed: int = 42, onset: int = 6) -> List[MetricSample]:
    """A slow, sustained p99 latency regression starting at step `onset`."""
    def latency_fn(t, r):
        if t < onset:
            return BASELINE.p99_latency_ms * (1.0 + r.uniform(-0.05, 0.05))
        growth = 1.0 + 0.15 * (t - onset)
        return BASELINE.p99_latency_ms * growth * (1.0 + r.uniform(-0.05, 0.05))
    return _sample_series(
        n,
        latency_fn,
        lambda t, r: max(0.0, BASELINE.error_rate + r.uniform(-0.001, 0.001)),
        lambda t, r: 1.0 + r.uniform(-0.2, 0.2),
        seed,
    )


def scenario_error_spike(n: int = 20, seed: int = 42, onset: int = 8) -> List[MetricSample]:
    """A sharp, sustained HTTP 5xx error-rate spike starting at step `onset`."""
    def error_fn(t, r):
        if t < onset:
            return max(0.0, BASELINE.error_rate + r.uniform(-0.001, 0.001))
        return 0.06 + r.uniform(-0.005, 0.01)
    return _sample_series(
        n,
        lambda t, r: BASELINE.p99_latency_ms * (1.0 + r.uniform(-0.05, 0.05)),
        error_fn,
        lambda t, r: 1.0 + r.uniform(-0.2, 0.2),
        seed,
    )


def scenario_budget_exhaustion(n: int = 20, seed: int = 42, onset: int = 5) -> List[MetricSample]:
    """Error-budget burn-rate velocity climbs steadily starting at step `onset`,
    with latency and error rate remaining near baseline (the scenario the
    paper argues single-metric threshold systems tend to miss)."""
    def burn_fn(t, r):
        if t < onset:
            return 1.0 + r.uniform(-0.2, 0.2)
        return min(20.0, 2.0 * (t - onset + 1)) + r.uniform(-0.5, 0.5)
    return _sample_series(
        n,
        lambda t, r: BASELINE.p99_latency_ms * (1.0 + r.uniform(-0.05, 0.05)),
        lambda t, r: max(0.0, BASELINE.error_rate + r.uniform(-0.001, 0.001)),
        burn_fn,
        seed,
    )


def scenario_noisy_transient(n: int = 20, seed: int = 42, glitch_at: int = 10) -> List[MetricSample]:
    """A single-step transient latency/error glitch (e.g. a brief network
    hiccup) surrounded by otherwise healthy samples. A well-tuned controller
    should NOT roll back on this."""
    def latency_fn(t, r):
        base = BASELINE.p99_latency_ms * (1.0 + r.uniform(-0.05, 0.05))
        return base * 2.5 if t == glitch_at else base

    def error_fn(t, r):
        base = max(0.0, BASELINE.error_rate + r.uniform(-0.001, 0.001))
        return 0.08 if t == glitch_at else base

    return _sample_series(
        n,
        latency_fn,
        error_fn,
        lambda t, r: 1.0 + r.uniform(-0.2, 0.2),
        seed,
    )


SCENARIOS = {
    "healthy": scenario_healthy,
    "latency_degradation": scenario_latency_degradation,
    "error_spike": scenario_error_spike,
    "budget_exhaustion": scenario_budget_exhaustion,
    "noisy_transient": scenario_noisy_transient,
}


def h_series_for_scenario(name: str, n: int = 20, seed: int = 42) -> List[float]:
    """Generate a scenario's metric samples and reduce them to an H(t) series."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario '{name}', choices: {list(SCENARIOS)}")
    samples = SCENARIOS[name](n=n, seed=seed)
    return [health_index(s, BASELINE) for s in samples]
