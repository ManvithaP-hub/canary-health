---
title: 'canary-health: A Reference Implementation of Dynamic, Multi-Metric Canary Deployment Health Scoring and Automated Rollback'
tags:
  - Python
  - Kubernetes
  - DevOps
  - continuous delivery
  - canary deployment
  - site reliability engineering
authors:
  - name: Manvitha Potluri
    orcid: 0009-0006-3209-7857
    affiliation: 1
affiliations:
  - name: 24x7 Systems
    index: 1
date: 10 September 2026
bibliography: paper.bib
---

# Summary

Canary deployment is a widely used technique for reducing the risk of
shipping a faulty software release: a new version is exposed to a small
fraction of production traffic before being promoted to serve all
traffic. In common practice, this is implemented with static rules — a
fixed traffic percentage held for a fixed observation window, and a
rollback triggered only when a single metric (typically an HTTP error
rate) crosses a fixed threshold. Static rules are simple to reason about
but are also known to miss regressions that manifest as latency
degradation, multi-metric interactions, or slow error-budget burn rather
than a sharp spike in one signal, and they cannot adapt their pace to
how quickly a regression is (or is not) unfolding.

`canary-health` is a small, dependency-free Python package that
implements an alternative: a continuously computed health index
`H(t) = 1 - Σ w_j · m_j(t)`, where each `m_j(t)` is a normalized penalty
function over a telemetry signal (p99 latency degradation, HTTP 5xx
error-rate surge, and SLO error-budget burn-rate velocity) and `w_j` are
configurable weights. A finite-state controller consumes the resulting
`H(t)` stream and drives a canary through `INITIAL_PROBE`, `RAMP_UP`,
`ROLLBACK`, and `PROMOTED` states using two configurable thresholds
(`theta1`, `theta2`), a moving-average smoothing window, and a
consecutive-breach debounce intended to absorb transient telemetry
noise without suppressing genuine regressions. The package ships five
deterministic synthetic scenario generators (a healthy rollout, latency
degradation, an error-rate spike, error-budget exhaustion, and a
single-step noisy transient) that are used both as a test fixture and
as a reproducible quantitative evaluation harness, and an optional,
dry-run-by-default integration that translates a controller decision
into a `kubectl` command against an Istio `VirtualService` or an Argo
Rollouts canary resource.

# Statement of need

Progressive-delivery tooling such as Flagger [@flagger] and Argo
Rollouts [@argorollouts] already provides production-grade traffic
shifting and metric-threshold rollback for Kubernetes. `canary-health`
is not a replacement for that tooling; it does not manage live traffic
on its own and does not implement a Kubernetes controller/operator
loop. Instead, it packages a small, inspectable, and independently
testable implementation of the *health-scoring and decision logic* —
the H(t) index and the state machine that decides when to hold,
advance, or roll back — described in the accompanying research paper
[@potluri2026canary], separated from any particular mesh or CI/CD
integration.

This separation serves two audiences. Researchers and practitioners
evaluating multi-metric, adaptive alternatives to static canary
thresholds can run the scenario generators and inspect exactly how
changes to weights, thresholds, or the smoothing/debounce parameters
change rollback latency and false-positive behavior, without needing a
live cluster. Platform engineers building or extending progressive
delivery automation (for example, as a component inside an existing
Flagger or Argo Rollouts workflow, or a custom controller) can import
`health_index()` and `CanaryController` directly as a well-tested
building block, and use the `traffic.py` module's dry-run command
generation as a starting point for wiring the controller's decisions
into a real mesh.

The error-budget burn-rate penalty and its default critical-burn-rate
constant follow the fast-burn alerting convention described in the
Google SRE Workbook [@sre-workbook]. The package's test suite and
scenario harness also provide a concrete, reproducible answer to a
question that is easy to argue qualitatively but hard to demonstrate
quantitatively: whether a given smoothing and debounce configuration
actually distinguishes a genuine regression from a transient glitch.
Running all five scenarios (Section "Quantitative evaluation" of the
README) shows the three genuine-regression scenarios triggering
rollback within 12-19 simulated steps of a 30-step window, while the
single-glitch scenario reaches full promotion without a false rollback
— the direct, testable consequence of the debounce logic addressing
the noise-filtering concern raised in the accompanying paper
[@potluri2026canary].

# References
