"""canary_health: a reference implementation of a dynamic, multi-metric
canary-deployment health model and progressive-delivery controller.

This package implements the H(t) health index, penalty functions, and
state machine described in "AI-Driven Canary Deployments and Automated
Rollbacks in Kubernetes Environments" (Potluri, 2026), plus synthetic
scenario generators used to quantitatively evaluate the controller's
behavior.
"""

__version__ = "0.1.0"
