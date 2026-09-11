"""Command-line interface for canary_health.

    canary-health simulate --scenario error_spike --steps 20
    canary-health list-scenarios
"""
import argparse
import json
import sys
from typing import List, Optional

from .controller import CanaryController, ControllerConfig
from .simulator import h_series_for_scenario, SCENARIOS
from .traffic import istio_patch_command, argo_rollouts_set_weight_command, run_command


def cmd_simulate(args):
    h_series = h_series_for_scenario(args.scenario, n=args.steps, seed=args.seed)
    config = ControllerConfig(theta1=args.theta1, theta2=args.theta2)
    controller = CanaryController(config)
    log = controller.run(h_series)

    output = [
        {
            "t": r.t,
            "raw_h": round(r.raw_h, 4),
            "smoothed_h": round(r.smoothed_h, 4),
            "state": r.state.value,
            "traffic_pct": r.traffic_pct,
            "note": r.note,
        }
        for r in log
    ]

    if args.output:
        with open(args.output, "w") as f:
            json.dump(output, f, indent=2)
        print(f"wrote {len(output)} steps to {args.output}", file=sys.stderr)
    else:
        json.dump(output, sys.stdout, indent=2)
        print()

    final_state = log[-1].state.value if log else None
    print(f"\nscenario={args.scenario} final_state={final_state} steps_run={len(log)}", file=sys.stderr)

    if args.apply_traffic:
        weight = int(log[-1].traffic_pct)
        if args.mesh == "istio":
            cmd = istio_patch_command(args.virtual_service, args.namespace, 100 - weight, weight)
        else:
            cmd = argo_rollouts_set_weight_command(args.rollout, args.namespace, weight)
        print(run_command(cmd, apply=args.apply), file=sys.stderr)


def cmd_list_scenarios(args):
    for name in SCENARIOS:
        print(name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canary-health",
        description="Reference implementation of the H(t) progressive-delivery health model and controller.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sim = sub.add_parser("simulate", help="Run a synthetic scenario through the controller.")
    sim.add_argument("--scenario", choices=list(SCENARIOS), default="healthy")
    sim.add_argument("--steps", type=int, default=20)
    sim.add_argument("--seed", type=int, default=42)
    sim.add_argument("--theta1", type=float, default=ControllerConfig.theta1)
    sim.add_argument("--theta2", type=float, default=ControllerConfig.theta2)
    sim.add_argument("--output", type=str, default=None, help="write JSON step log to a file instead of stdout")
    sim.add_argument("--apply-traffic", action="store_true", help="also emit a mesh traffic-weight command for the final state")
    sim.add_argument("--mesh", choices=["istio", "argo-rollouts"], default="istio")
    sim.add_argument("--virtual-service", default="my-service")
    sim.add_argument("--rollout", default="my-rollout")
    sim.add_argument("--namespace", default="default")
    sim.add_argument("--apply", action="store_true", help="actually execute the kubectl command (default: dry-run/print only)")
    sim.set_defaults(func=cmd_simulate)

    ls = sub.add_parser("list-scenarios", help="List available synthetic evaluation scenarios.")
    ls.set_defaults(func=cmd_list_scenarios)

    return parser


def main(argv: Optional[List[str]] = None):
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
