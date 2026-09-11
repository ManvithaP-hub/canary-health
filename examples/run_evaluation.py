#!/usr/bin/env python3
"""Runs all five synthetic scenarios through the controller and prints a
markdown results table. This is the script used to produce the
quantitative-evaluation numbers referenced in the paper's evaluation
section.

Usage:
    python examples/run_evaluation.py [--steps N] [--seed N]
"""
import argparse

from canary_health.controller import CanaryController, ControllerConfig
from canary_health.simulator import SCENARIOS, h_series_for_scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rows = []
    for name in SCENARIOS:
        series = h_series_for_scenario(name, n=args.steps, seed=args.seed)
        controller = CanaryController(ControllerConfig())
        log = controller.run(series)
        final = log[-1]
        rows.append(
            {
                "scenario": name,
                "final_state": final.state.value,
                "steps_to_decision": len(log),
                "final_traffic_pct": final.traffic_pct,
                "final_smoothed_h": round(final.smoothed_h, 3),
            }
        )

    header = "| Scenario | Final state | Steps to decision | Final traffic % | Final H(t) |"
    sep = "|---|---|---|---|---|"
    print(header)
    print(sep)
    for r in rows:
        print(
            f"| {r['scenario']} | {r['final_state']} | {r['steps_to_decision']}/{args.steps} "
            f"| {r['final_traffic_pct']:.1f}% | {r['final_smoothed_h']} |"
        )


if __name__ == "__main__":
    main()
