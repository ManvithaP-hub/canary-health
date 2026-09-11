from canary_health.simulator import h_series_for_scenario, SCENARIOS
from canary_health.controller import CanaryController, ControllerConfig, State


def test_all_scenarios_produce_bounded_series():
    for name in SCENARIOS:
        series = h_series_for_scenario(name, n=15)
        assert len(series) == 15
        assert all(0.0 <= h <= 1.0 for h in series)


def test_series_is_deterministic_for_a_given_seed():
    a = h_series_for_scenario("error_spike", n=20, seed=7)
    b = h_series_for_scenario("error_spike", n=20, seed=7)
    assert a == b


def test_healthy_scenario_stays_above_theta1():
    series = h_series_for_scenario("healthy", n=20)
    assert min(series) > 0.85


def test_error_spike_scenario_triggers_rollback():
    series = h_series_for_scenario("error_spike", n=20)
    controller = CanaryController(ControllerConfig())
    log = controller.run(series)
    assert log[-1].state == State.ROLLBACK


def test_latency_degradation_scenario_triggers_rollback():
    series = h_series_for_scenario("latency_degradation", n=25)
    controller = CanaryController(ControllerConfig())
    log = controller.run(series)
    assert log[-1].state == State.ROLLBACK


def test_budget_exhaustion_scenario_triggers_rollback():
    series = h_series_for_scenario("budget_exhaustion", n=20)
    controller = CanaryController(ControllerConfig())
    log = controller.run(series)
    assert log[-1].state == State.ROLLBACK


def test_noisy_transient_scenario_does_not_trigger_rollback():
    series = h_series_for_scenario("noisy_transient", n=20)
    controller = CanaryController(ControllerConfig())
    log = controller.run(series)
    assert log[-1].state != State.ROLLBACK
