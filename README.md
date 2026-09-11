# canary-health

A reference implementation of a dynamic, multi-metric health model and
automated-rollback controller for progressive delivery in Kubernetes,
implementing the `H(t)` health index and state machine described in
*AI-Driven Canary Deployments and Automated Rollbacks in Kubernetes
Environments* (Potluri, 2026).

Static canary deployments hold a fixed percentage of traffic for a fixed
time window and rely on single-metric thresholds (e.g., "roll back if
error rate exceeds 5%"). This package implements the alternative
described in the paper: a continuously computed health index that
combines several normalized telemetry signals, and a controller that
uses it to decide, at every step, whether to hold, ramp up, or roll back
a canary release.

## What's in here

- **`canary_health/health.py`** — the health index `H(t) = 1 - Σ w_j·m_j(t)`,
  plus three penalty functions `m_j` for p99 latency degradation, HTTP
  5xx error-rate surge, and SLO error-budget burn-rate velocity.
- **`canary_health/controller.py`** — the `INITIAL_PROBE → RAMP_UP →
  PROMOTED` / `ROLLBACK` state machine, with a moving-average smoothing
  window and a consecutive-breach debounce so a single noisy sample
  doesn't trigger an unnecessary rollback.
- **`canary_health/simulator.py`** — five deterministic synthetic
  scenarios (healthy rollout, latency degradation, error spike, budget
  exhaustion, and a noisy single-step transient) used to exercise and
  quantitatively evaluate the controller.
- **`canary_health/traffic.py`** — optional, dry-run-by-default
  integration that turns a controller's decision into a real `kubectl`
  command against an Istio `VirtualService` or an Argo Rollouts canary.
- **`canary_health/cli.py`** — the `canary-health` command-line tool.

## Install

```bash
git clone https://github.com/ManvithaP-hub/canary-health.git
cd canary-health
pip install -e ".[dev]"
```

Requires Python 3.9+. The core package has no runtime dependencies
beyond the standard library; `pytest` is only needed for running the
test suite.

## Usage

List the available evaluation scenarios:

```bash
canary-health list-scenarios
```

Run one through the controller:

```bash
canary-health simulate --scenario error_spike --steps 20
```

This prints a step-by-step JSON log (raw `H(t)`, smoothed `H(t)`,
controller state, traffic percentage, and a human-readable note for each
step) to stdout, and a one-line summary to stderr.

Also emit the `kubectl` command that would apply the final traffic
weight to a live Istio `VirtualService` (dry-run by default — nothing is
executed unless `--apply` is also passed):

```bash
canary-health simulate --scenario healthy --steps 20 \
    --apply-traffic --mesh istio --virtual-service my-service --namespace prod
```

As a library:

```python
from canary_health.health import MetricSample, Baseline, health_index
from canary_health.controller import CanaryController, ControllerConfig

baseline = Baseline(p99_latency_ms=120.0, error_rate=0.002)
sample = MetricSample(p99_latency_ms=180.0, error_rate=0.01, budget_burn_rate=3.0)

h = health_index(sample, baseline)  # -> float in [0, 1]

controller = CanaryController(ControllerConfig(theta1=0.90, theta2=0.75))
result = controller.step(t=0, raw_h=h)
print(result.state, result.traffic_pct, result.note)
```

## Quantitative evaluation

The paper's original evaluation was qualitative. Running all five
scenarios through the controller (30 steps, default thresholds
`theta1=0.90`, `theta2=0.75`, smoothing window 3, 2-step debounce)
produces:

```
python examples/run_evaluation.py
```

| Scenario | Final state | Steps to decision | Final traffic % | Final H(t) |
|---|---|---|---|---|
| healthy | promoted | 30/30 | 100.0% | 0.997 |
| latency_degradation | rollback | 19/30 | 0.0% | 0.710 |
| error_spike | rollback | 12/30 | 0.0% | 0.739 |
| budget_exhaustion | rollback | 15/30 | 0.0% | 0.747 |
| noisy_transient | promoted | 30/30 | 100.0% | 0.997 |

The three genuine regressions (latency, error, and budget-burn
scenarios) are each caught and rolled back well before the 30-step
window ends, at speeds proportional to how sharply each signal departs
from baseline (the error spike is caught fastest since it is the
steepest onset). The `noisy_transient` scenario — a single glitched
sample surrounded by healthy ones — reaches full promotion rather than
triggering a false rollback, which is the direct, testable consequence
of the smoothing and debounce logic addressing the "Metric Granularity
and Noise" concern raised in the paper's Section 5.

## Testing

```bash
pytest
```

26 tests cover the penalty functions and health index (boundary
behavior, clamping, weight validation), the controller state machine
(promotion, rollback, debounce, terminal-state handling), and the
scenario generators (determinism, bounds, and end-to-end controller
behavior per scenario).

## Relationship to the paper's model

| Paper concept | Implementation |
|---|---|
| `H(t) = 1 - Σ w_j·m_j(t)` | `health.health_index()` |
| Normalized penalty functions `m_j(t)` | `health.latency_penalty()`, `health.error_penalty()`, `health.budget_burn_penalty()` |
| `θ1`, `θ2` operational thresholds | `controller.ControllerConfig.theta1` / `.theta2` |
| Initial Probe / Graduated Ramp-Up / Immediate Rollback states | `controller.State` |
| Progressive Traffic Splitter Layer | `traffic.py` (Istio / Argo Rollouts backends) |
| "filter transient noise" governance requirement | smoothing window + consecutive-breach debounce in `controller.py` |

The weights (`0.35` latency / `0.40` error rate / `0.25` budget burn)
and default thresholds are illustrative starting points, not values
derived from production data — they are exposed as configuration
(`ControllerConfig`, the `weights` argument to `health_index`) precisely
because the right values are workload-dependent and are expected to be
tuned per-service in practice.

## License

Apache License 2.0. See [LICENSE](LICENSE).

## Citation

If you use this software, please cite:

Potluri, M. (2026). *AI-Driven Canary Deployments and Automated
Rollbacks in Kubernetes Environments.*
