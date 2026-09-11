"""Progressive-delivery controller: the discrete operational state machine
driven by H(t), as described in the paper's Section 3.

States:
  INITIAL_PROBE  - H(t) >= theta1 not yet sustained; holding at initial traffic %.
  RAMP_UP        - theta1 <= H(t): traffic increments toward 100%.
  ROLLBACK       - H(t) < theta2 (sustained): traffic reverted to 0%, terminal.
  PROMOTED       - traffic has reached 100% with sustained health, terminal.

Two guardrails are implemented on top of the paper's model to address the
paper's own "Metric Granularity and Noise" consideration (Section 5):
  - a moving-average smoothing window over raw H(t) samples, and
  - a debounce requiring `consecutive_breaches_required` smoothed samples
    below theta2 before a rollback fires,
so that a single transient glitch does not trigger an unnecessary rollback.
"""
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import List


class State(str, Enum):
    INITIAL_PROBE = "initial_probe"
    RAMP_UP = "ramp_up"
    ROLLBACK = "rollback"
    PROMOTED = "promoted"


@dataclass
class ControllerConfig:
    theta1: float = 0.90                 # health threshold to ramp up traffic
    theta2: float = 0.75                 # health threshold below which rollback fires
    initial_traffic_pct: float = 5.0
    ramp_step_pct: float = 15.0
    smoothing_window: int = 3            # moving-average window over raw H(t)
    consecutive_breaches_required: int = 2  # debounce before declaring rollback


@dataclass
class StepResult:
    t: int
    raw_h: float
    smoothed_h: float
    state: State
    traffic_pct: float
    note: str = ""


class CanaryController:
    """Drives canary traffic weight forward from a stream of H(t) values."""

    def __init__(self, config: ControllerConfig = None):
        self.config = config or ControllerConfig()
        self.state = State.INITIAL_PROBE
        self.traffic_pct = self.config.initial_traffic_pct
        self._h_history: List[float] = []
        self._breach_count = 0
        self.log: List[StepResult] = []

    def _smoothed(self, raw_h: float) -> float:
        self._h_history.append(raw_h)
        window = self._h_history[-self.config.smoothing_window:]
        return statistics.fmean(window)

    def step(self, t: int, raw_h: float) -> StepResult:
        if self.state == State.ROLLBACK:
            result = StepResult(t, raw_h, raw_h, self.state, self.traffic_pct, "terminal: already rolled back")
            self.log.append(result)
            return result

        smoothed = self._smoothed(raw_h)
        note = ""

        if smoothed < self.config.theta2:
            self._breach_count += 1
        else:
            self._breach_count = 0

        if self._breach_count >= self.config.consecutive_breaches_required:
            self.state = State.ROLLBACK
            self.traffic_pct = 0.0
            note = (
                f"rollback triggered: smoothed H={smoothed:.3f} breached "
                f"theta2={self.config.theta2} for {self._breach_count} consecutive steps"
            )
        elif smoothed >= self.config.theta1:
            if self.state == State.INITIAL_PROBE:
                self.state = State.RAMP_UP
            if self.state == State.RAMP_UP:
                self.traffic_pct = min(100.0, self.traffic_pct + self.config.ramp_step_pct)
                if self.traffic_pct >= 100.0:
                    self.state = State.PROMOTED
                    note = "promoted: 100% traffic reached with sustained health"
                else:
                    note = f"ramp-up: traffic increased to {self.traffic_pct:.1f}%"
        else:
            note = f"holding: smoothed H={smoothed:.3f} in [{self.config.theta2}, {self.config.theta1})"

        result = StepResult(t, raw_h, smoothed, self.state, self.traffic_pct, note)
        self.log.append(result)
        return result

    def run(self, h_series: List[float]) -> List[StepResult]:
        """Feed a full H(t) series through the controller, stopping early
        if a rollback fires (rollback is a terminal state for a single
        deployment attempt)."""
        for t, raw_h in enumerate(h_series):
            self.step(t, raw_h)
            if self.state == State.ROLLBACK:
                break
        return self.log
