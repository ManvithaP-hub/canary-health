from canary_health.controller import CanaryController, ControllerConfig, State


def test_healthy_series_reaches_promoted():
    controller = CanaryController(ControllerConfig(smoothing_window=1, consecutive_breaches_required=1))
    h_series = [0.98] * 10
    log = controller.run(h_series)
    assert log[-1].state == State.PROMOTED
    assert log[-1].traffic_pct == 100.0


def test_degrading_series_triggers_rollback():
    controller = CanaryController(ControllerConfig(smoothing_window=1, consecutive_breaches_required=1))
    h_series = [0.95, 0.90, 0.60, 0.40]
    log = controller.run(h_series)
    assert log[-1].state == State.ROLLBACK
    assert log[-1].traffic_pct == 0.0


def test_single_transient_glitch_does_not_trigger_rollback():
    # A single very-low sample surrounded by healthy ones should be
    # absorbed by smoothing + the consecutive-breach debounce.
    config = ControllerConfig(smoothing_window=3, consecutive_breaches_required=2, theta1=0.9, theta2=0.7)
    controller = CanaryController(config)
    h_series = [0.97, 0.97, 0.97, 0.20, 0.97, 0.97, 0.97, 0.97]
    log = controller.run(h_series)
    assert log[-1].state != State.ROLLBACK


def test_rollback_is_terminal_and_stops_the_run():
    controller = CanaryController(ControllerConfig(smoothing_window=1, consecutive_breaches_required=1))
    h_series = [0.30, 0.30, 0.99, 0.99]  # health recovers after the breach; should not matter
    log = controller.run(h_series)
    assert log[-1].state == State.ROLLBACK
    assert len(log) == 1  # run() stops iterating once rollback fires


def test_traffic_never_exceeds_100():
    controller = CanaryController(
        ControllerConfig(smoothing_window=1, consecutive_breaches_required=1, ramp_step_pct=40)
    )
    h_series = [0.99] * 10
    log = controller.run(h_series)
    assert all(r.traffic_pct <= 100.0 for r in log)


def test_initial_state_and_traffic():
    controller = CanaryController()
    assert controller.state == State.INITIAL_PROBE
    assert controller.traffic_pct == ControllerConfig().initial_traffic_pct
