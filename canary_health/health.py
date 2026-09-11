"""Health scoring model.

Implements H(t) = 1 - sum_j( w_j * m_j(t) ), the weighted multi-metric
health index from the paper's formal model, where each m_j(t) is a
normalized penalty function bounded to [0, 1] and the weights w_j sum
to 1.

Three penalty functions are provided out of the box, corresponding to
the metric families named in the paper: p99 latency degradation, HTTP
5xx error-rate surge, and error-budget burn-rate velocity. Each is a
plain function of (observed, baseline, ...) so they can be tested and
reused independently of the health_index() aggregator.
"""
from dataclasses import dataclass
from typing import Dict, Optional


DEFAULT_WEIGHTS: Dict[str, float] = {
    "latency": 0.35,
    "error_rate": 0.40,
    "budget_burn": 0.25,
}


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def latency_penalty(p99_ms: float, baseline_p99_ms: float, ceiling_ratio: float = 3.0) -> float:
    """Normalized penalty for p99 latency degradation relative to baseline.

    0.0 when p99 <= baseline; rises linearly to 1.0 as p99 approaches
    ceiling_ratio * baseline (default: 3x baseline is treated as maximally
    unhealthy).
    """
    if baseline_p99_ms <= 0:
        return 0.0
    ratio = p99_ms / baseline_p99_ms
    if ratio <= 1.0:
        return 0.0
    penalty = (ratio - 1.0) / (ceiling_ratio - 1.0)
    return clamp(penalty)


def error_penalty(error_rate: float, baseline_error_rate: float, ceiling: float = 0.10) -> float:
    """Normalized penalty for HTTP 5xx error-rate surge above baseline.

    0.0 at or below baseline; 1.0 once error_rate reaches `ceiling`
    (default: 10% error rate is treated as maximally unhealthy).
    """
    delta = max(0.0, error_rate - baseline_error_rate)
    denom = max(ceiling - baseline_error_rate, 1e-6)
    return clamp(delta / denom)


def budget_burn_penalty(burn_rate: float, critical_burn_rate: float = 14.4) -> float:
    """Normalized penalty for error-budget burn-rate velocity.

    burn_rate == 1.0 means the SLO budget is being consumed at exactly
    the sustainable rate; 0.0 or below means no burn. critical_burn_rate
    is the multiple of the sustainable rate treated as maximally
    unhealthy (14.4x is the common SRE fast-burn alert threshold for a
    1-hour window against a 30-day budget).
    """
    if burn_rate <= 1.0:
        return 0.0
    penalty = (burn_rate - 1.0) / (critical_burn_rate - 1.0)
    return clamp(penalty)


@dataclass
class MetricSample:
    """A single point-in-time observation of the canary's telemetry."""
    p99_latency_ms: float
    error_rate: float
    budget_burn_rate: float


@dataclass
class Baseline:
    """The stable release's reference metrics that the canary is compared against."""
    p99_latency_ms: float
    error_rate: float


def compute_penalties(sample: MetricSample, baseline: Baseline) -> Dict[str, float]:
    return {
        "latency": latency_penalty(sample.p99_latency_ms, baseline.p99_latency_ms),
        "error_rate": error_penalty(sample.error_rate, baseline.error_rate),
        "budget_burn": budget_burn_penalty(sample.budget_burn_rate),
    }


def health_index(sample: MetricSample, baseline: Baseline, weights: Optional[Dict[str, float]] = None) -> float:
    """Compute H(t) = 1 - sum_j(w_j * m_j(t)) for a single sample.

    Raises ValueError if the supplied weights don't sum to 1.0, matching
    the constraint stated in the paper's formal model.
    """
    weights = weights or DEFAULT_WEIGHTS
    total_weight = sum(weights.values())
    if abs(total_weight - 1.0) > 1e-6:
        raise ValueError(f"weights must sum to 1.0, got {total_weight}")

    penalties = compute_penalties(sample, baseline)
    weighted_penalty = sum(weights[k] * penalties[k] for k in weights)
    return clamp(1.0 - weighted_penalty)
