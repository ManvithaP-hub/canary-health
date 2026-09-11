"""Optional integration for applying a controller's computed traffic
weight to a live service mesh. Two backends are provided: an Istio
VirtualService (patched via `kubectl patch`) and an Argo Rollouts
canary (via `kubectl argo rollouts set weight`).

Every command defaults to dry-run: it is built and returned as a string
for inspection/logging, and only actually executed via subprocess when
apply=True is passed explicitly. This mirrors the automated-rollback
engine's requirement (paper Section 5) that every action be auditable.
"""
import shlex
import subprocess
from typing import List


def istio_patch_command(virtual_service: str, namespace: str, stable_weight: int, canary_weight: int) -> List[str]:
    """Build a `kubectl patch` command that sets an Istio VirtualService's
    two-route traffic split (stable at index 0, canary at index 1)."""
    patch = (
        '[{"op":"replace","path":"/spec/http/0/route/0/weight","value":%d},'
        '{"op":"replace","path":"/spec/http/0/route/1/weight","value":%d}]'
        % (stable_weight, canary_weight)
    )
    return [
        "kubectl", "patch", "virtualservice", virtual_service,
        "-n", namespace, "--type=json", "-p", patch,
    ]


def argo_rollouts_set_weight_command(rollout: str, namespace: str, canary_weight: int) -> List[str]:
    """Build a `kubectl argo rollouts set weight` command for an Argo
    Rollouts canary resource."""
    return [
        "kubectl", "argo", "rollouts", "set", "weight", rollout,
        str(canary_weight), "-n", namespace,
    ]


def run_command(cmd: List[str], apply: bool = False) -> str:
    """Return the command as a printable string in dry-run mode; execute
    it via subprocess and return its output only when apply=True."""
    printable = " ".join(shlex.quote(c) for c in cmd)
    if not apply:
        return f"[dry-run] {printable}"
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return f"[error] {printable}\n{result.stderr.strip()}"
    return f"[applied] {printable}\n{result.stdout.strip()}"
