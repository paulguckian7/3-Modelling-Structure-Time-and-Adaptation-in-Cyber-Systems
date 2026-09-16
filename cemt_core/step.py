"""
Trial step loop with STA ablation and the locked collapse rule.

Step ordering (unchanged from Code80 spec section 11):
  H0 phantom update            (open boundary only, never in deterministic)
  H1 infected -> compromised   (the one-step detection window, Time)
  H2 exfiltration by dwell     (Time)
  H3 drift -> execution gate   (Time -> Structure coupling)
  L2 systematic propagation    (Structure)
  L3 systemic cascade          (Structure)
  L4 drift accumulation        (Time)
  L5 adaptation                (Adaptation)
  audit, stop test

Ablation (Paper 2 pre-registered handoff):
  structure=False  L2 and L3 do not run: entry node only, no traversal
  time=False       no drift, no exfil dwell, infected activate immediately
  adaptation=False L5 does not run: a(t) fixed at 1, no remediation

Deterministic output (correspondence tier 1) is `reached` in order, and
`planes_owned` in order. Both are compared exactly against the Docker probe.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from .layers import (NodeState, SystemState, activate_infected, apply_delta,
                     exfiltrate_dwell, init_state, layer1_entry,
                     layer2_systematic, layer3_systemic, layer4_temporal,
                     layer5_adaptation, update_exec_modifier, update_phantoms,
                     x_obs, x_true)
from .network import NetworkState, build_network
from .spec import ScenarioSpec

COLLAPSE_X_THRESHOLD = 0.30
COLLAPSE_SUSTAIN_STEPS = 3


def classify_collapse(x_series: List[float],
                      threshold: float = COLLAPSE_X_THRESHOLD,
                      sustain: int = COLLAPSE_SUSTAIN_STEPS) -> int:
    """Return the step index at which sustained collapse is confirmed, or -1."""
    run = 0
    for i, x in enumerate(x_series):
        run = run + 1 if x >= threshold else 0
        if run >= sustain:
            return i
    return -1


def run_one_trial(net: NetworkState, rng: np.random.Generator,
                  entry: Optional[int] = None) -> Dict:
    spec = net.spec
    ab = spec.ablation
    st = init_state(net)

    # entry node: spec-pinned, else uniform over nodes with an Interface
    if entry is None:
        if spec.entry_node is not None:
            entry = net.index[spec.entry_node]
        else:
            cands = np.flatnonzero(net.interface & ~net.external)
            entry = int(rng.choice(cands)) if cands.size else 0

    d1 = layer1_entry(net, st, entry, rng)
    if d1 is not None:
        apply_delta(net, st, d1)

    for step in range(1, spec.time.max_steps + 1):
        st.step = step
        update_phantoms(net, st, rng)
        activate_infected(st)
        if ab.time:
            exfiltrate_dwell(net, st)
            update_exec_modifier(net, st)

        if ab.structure:
            apply_delta(net, st, layer2_systematic(net, st, rng))
            apply_delta(net, st, layer3_systemic(net, st, rng))
        if ab.time:
            apply_delta(net, st, layer4_temporal(net, st))
        n_rem = 0
        if ab.adaptation:
            d5 = layer5_adaptation(net, st, rng)
            apply_delta(net, st, d5)
            n_rem = d5.n_remediated
        if not ab.time:
            activate_infected(st)      # no detection window without Time

        st.audit["step"].append(step)
        st.audit["x_true"].append(x_true(net, st))
        st.audit["x_obs"].append(x_obs(net, st))
        st.audit["remediated"].append(n_rem)
        st.audit["drift_mean"].append(float(st.drift[~net.external].mean()))

        pending = (
            (st.compromise == NodeState.COMPROMISED).any()
            or (st.compromise == NodeState.INFECTED).any()
        )
        if not pending:
            break

    xs = st.audit["x_true"]
    xo = st.audit["x_obs"]
    t_collapse = classify_collapse(xs)
    # Time outcome: step of first observation, and fraction reached by then
    first_obs = next((i + 1 for i, v in enumerate(xo) if v > 0), -1)
    est = ~net.external
    if first_obs > 0:
        reached_by_then = sum(1 for s_, n_, _ in st.audit["reached"]
                              if s_ <= first_obs and not net.external[net.index[n_]])
        frac_before_obs = reached_by_then / max(int(est.sum()), 1)
    else:
        frac_before_obs = float(np.isin(st.compromise, [1, 2, 3])[est].mean())
    reached_mask = np.isin(st.compromise, [1, 2, 3])          # all nodes
    impact_mask = reached_mask & est                          # estate only
    return {
        "entry": net.ids[entry],
        "reached": list(st.audit["reached"]),          # (step, node, via)
        "reached_set": sorted(net.ids[j] for j in np.flatnonzero(reached_mask)),
        "planes_owned": list(st.audit["planes_owned"]),
        "x_true_final": xs[-1] if xs else 0.0,
        "x_true_max": max(xs) if xs else 0.0,
        "impact_true": float(net.impact[impact_mask].sum()),
        "t_collapse": t_collapse,
        "first_observed_step": first_obs,
        "frac_reached_before_observation": frac_before_obs,
        "n_remediations": len(st.audit.get("remediations", [])),
        "revocations": list(st.audit.get("revocations", [])),
        "first_remediation_step": (st.audit["remediations"][0][0]
                                   if st.audit.get("remediations") else -1),
        "collapsed": t_collapse >= 0,
        "n_steps": len(xs),
        "ablation": ab.label,
        "audit": st.audit,
    }


def run_scenario(spec: ScenarioSpec, n_trials: int = 1,
                 seed: Optional[int] = None) -> List[Dict]:
    seed = spec.seed if seed is None else seed
    net = build_network(spec, np.random.default_rng(seed))
    out = []
    for t in range(n_trials):
        out.append(run_one_trial(net, np.random.default_rng(seed * 100_003 + t)))
    return out


def summarise(results: List[Dict]) -> Dict:
    n = len(results)
    return {
        "n_trials": n,
        "collapse_rate": sum(r["collapsed"] for r in results) / max(n, 1),
        "mean_x_true_final": float(np.mean([r["x_true_final"] for r in results])),
        "mean_x_true_max": float(np.mean([r["x_true_max"] for r in results])),
        "mean_steps": float(np.mean([r["n_steps"] for r in results])),
    }
