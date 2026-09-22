"""Extended evaluation: static-threshold baselines, smoothing ablation, 100-seed robustness, and early-onset exposure. Uses canary-health unmodified."""
import statistics, json
from canary_health.controller import CanaryController, ControllerConfig, State
from canary_health.simulator import (SCENARIOS, BASELINE, scenario_healthy, scenario_latency_degradation,
    scenario_error_spike, scenario_budget_exhaustion, scenario_noisy_transient)
from canary_health.health import health_index

N=30
REGRESSIONS={"latency_degradation","error_spike","budget_exhaustion"}
ONSET={"latency_degradation":6,"error_spike":8,"budget_exhaustion":5,"noisy_transient":None,"healthy":None}

def gen(name, seed, onset=None):
    f=SCENARIOS[name]
    if onset is not None and name in REGRESSIONS:
        return f(n=N, seed=seed, onset=onset)
    return f(n=N, seed=seed)

def run_hindex(samples, cfg=None):
    c=CanaryController(cfg or ControllerConfig())
    prev=c.traffic_pct; exposure=None; promo=None
    for t,s in enumerate(samples):
        before=c.traffic_pct
        r=c.step(t, health_index(s, BASELINE))
        if r.state==State.PROMOTED and promo is None: promo=t
        if r.state==State.ROLLBACK:
            return dict(outcome="rollback", t=t, exposure=before, promo=promo)
    return dict(outcome="promoted" if c.state==State.PROMOTED else c.state.value, t=None, exposure=None, promo=promo)

def run_static(samples, err_thr=0.05, lat_mult=None):
    """Static canary: same ramp schedule (5% then +15%/step), fixed raw thresholds, no smoothing."""
    traffic=5.0; promo=None
    for t,s in enumerate(samples):
        breach = s.error_rate>err_thr or (lat_mult is not None and s.p99_latency_ms>lat_mult*BASELINE.p99_latency_ms)
        if breach:
            return dict(outcome="rollback", t=t, exposure=traffic, promo=promo)
        traffic=min(100.0, traffic+15.0)
        if traffic>=100 and promo is None: promo=t
    return dict(outcome="promoted", t=None, exposure=None, promo=promo)

CONTROLLERS={
 "H(t) controller": lambda s: run_hindex(s),
 "Static: error>5%": lambda s: run_static(s, 0.05, None),
 "Static: error>5% or p99>2x": lambda s: run_static(s, 0.05, 2.0),
 "H(t), no smoothing/debounce": lambda s: run_hindex(s, ControllerConfig(smoothing_window=1, consecutive_breaches_required=1)),
}

out={}
# Exp A: default scenarios, seed 42
A={}
for name in SCENARIOS:
    A[name]={k:f(gen(name,42)) for k,f in CONTROLLERS.items()}
out["A"]=A
# Exp B: early onset (regression present from first sample)
B={}
for name in REGRESSIONS:
    B[name]={k:f(gen(name,42,onset=0)) for k,f in CONTROLLERS.items()}
out["B"]=B
# Exp C: 100 seeds, default onset and early onset
def agg(onset_mode):
    res={}
    for k,f in CONTROLLERS.items():
        row={}
        for name in SCENARIOS:
            outs=[f(gen(name,seed, 0 if (onset_mode=="early" and name in REGRESSIONS) else None)) for seed in range(100)]
            rb=[o for o in outs if o["outcome"]=="rollback"]
            if name in REGRESSIONS:
                on = 0 if onset_mode=="early" else ONSET[name]
                delays=[o["t"]-on for o in rb]
                row[name]=dict(detect=len(rb), mean_delay=round(statistics.fmean(delays),2) if delays else None,
                               mean_exposure=round(statistics.fmean([o["exposure"] for o in rb]),1) if rb else None)
            else:
                row[name]=dict(false_rollbacks=len(rb))
        res[k]=row
    return res
out["C_default"]=agg("default"); out["C_early"]=agg("early")
print(json.dumps(out, indent=1))
