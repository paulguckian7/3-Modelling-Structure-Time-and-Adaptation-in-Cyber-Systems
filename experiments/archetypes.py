"""
Archetype experiments for Paper 3A, Sections V to VIII.

  python -m experiments.archetypes            build specs, run, write tables
  python -m experiments.archetypes --seeds 50

Each experiment names one manipulated variable, one primary outcome and one
intervention signature (a Boolean contrast). The ablation matrix runs every
experiment under M_STA, M_ST, M_SA, M_S and M_TA and records whether the
signature is present, which is the H4/H5 test of the manuscript.

Experiment 1, Structure (WannaCry-inspired). Population of admitting nodes.
  S1 flat: one zone, all pairwise connected.
  S2 segmented: three zones, no shared node.
  S3 isolated critical population: main zone plus a zone with no Connection
     to it.
  S4 redundant pathway: S2 plus one Channel across the segmentation.
  Manipulated: R. Primary outcome: reached set (deterministic).
  Signature: reached_set(S1) != reached_set(S2).

Experiment 2, Time (CrowdStrike-inspired). External vendor directing a
population of agents with local X and A; high fan-out.
  T1 immediate: the plane pushes to the whole population in one step.
  T2 staged: canary subset first, remainder after an interval.
  Manipulated: rollout schedule. Primary outcome: fraction of the population
  reached before the first observation (deterministic; latency fixed).
  Signature: frac(T2) < frac(T1).

Experiment 3, Adaptation (SolarWinds-inspired). External vendor directing
build agents; each agent has Channel routes to dependent services.
  Open loop:  u(t) = 0 (adaptation ablated).
  Closed loop, remediation only: remediate observed nodes when o(t) > theta_d.
  Closed loop, revoke trust: additionally withdraw the admission configured
     for a directing controller whose members are observed compromised.
  Manipulated: the loop. Primary outcome: final extent at a fixed horizon,
  paired over seeds (stochastic). Signature: median paired difference
  (open - closed) > 0 and the closed-loop extent is lower in a majority of
  seeds. Remediation-only is reported as a secondary condition: under a
  persistent trusted source it is predicted NOT to change the outcome.

Ablation semantics (Section VIII): T off collapses the rollout interval and
the observation latency to 0 and removes the detection window; A off fixes
u(t)=0; S off disables Layers 2 and 3.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import sys
from typing import Dict, List

import numpy as np
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cemt_core.spec import (AblationSpec, AdaptationSpec, Condition, DefenderActionKind, Governance,
                            Node, RateSpec, Relation, RelationClass, ScenarioSpec,
                            TimeSpec, dump_spec)
from cemt_core.step import run_scenario

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "scenarios", "archetypes")
RES = os.path.join(os.path.dirname(HERE), "results")

GOV = [Governance("estate", True), Governance("vendor", False)]
MODELS = {
    "STA": AblationSpec(True, True, True),
    "ST":  AblationSpec(True, True, False),
    "SA":  AblationSpec(True, False, True),
    "S":   AblationSpec(True, False, False),
    "TA":  AblationSpec(False, True, True),
}
# rates for the stochastic runs; identical across every condition of an experiment
RATES = RateSpec(threat_capability=1.0, authority_rate=0.8, execution_rate=0.8,
                 beta_conn=0.5, dependency_factor=3.0, control_plane_takeover_rate=0.0)


def N(id, gov="estate", I=False, X=True, A=True, zones=(), vis=True, state="state"):
    return Node(id=id, governance=gov, interface=I, execution_pathway=X, authority=A,
                zones=list(zones), visible=vis, state_object=state)


def conn(a, b):
    return Relation(a, b, Condition.INTERFACE, RelationClass.CONNECTION)


def chan(u, d):
    return Relation(u, d, Condition.EXECUTION_PATHWAY, RelationClass.CHANNEL)


def cpd(c, m, g):
    return Relation(c, m, Condition.AUTHORITY, RelationClass.CONTROL_PLANE_DIRECTING,
                    conferral=True, group=g)


def clique(ids):
    return [conn(ids[i], ids[j]) for i in range(len(ids)) for j in range(i + 1, len(ids))]


# ---------------------------------------------------------- Experiment 1 ----

def exp1_specs() -> Dict[str, ScenarioSpec]:
    n = 24
    ids = [f"h{i:02d}" for i in range(n)]
    base = dict(governance=GOV, entry_node="h00", deterministic=True,
                time=TimeSpec(max_steps=40), rates=RATES, seed=1)
    out = {}
    # S1 flat
    nodes = [N("h00", I=True, zones=[0, 1])] + [N(i, zones=[1]) for i in ids[1:]]
    out["S1_flat"] = ScenarioSpec(id="e1_S1_flat", description="one zone, all reachable",
                                  nodes=nodes, relations=clique(ids), **base)
    # S2 segmented: 3 zones of 8, no shared node
    z = [ids[0:8], ids[8:16], ids[16:24]]
    nodes = [N("h00", I=True, zones=[0, 1])] + [N(i, zones=[1]) for i in z[0][1:]] \
        + [N(i, zones=[2]) for i in z[1]] + [N(i, zones=[3]) for i in z[2]]
    rels = clique(z[0]) + clique(z[1]) + clique(z[2])
    out["S2_segmented"] = ScenarioSpec(id="e1_S2_segmented", description="three zones, no shared node",
                                       nodes=nodes, relations=rels, **base)
    # S3 isolated critical population: main zone of 16 plus 8 critical with no Connection to it
    nodes = [N("h00", I=True, zones=[0, 1])] + [N(i, zones=[1]) for i in ids[1:16]] \
        + [N(i, zones=[9]) for i in ids[16:24]]
    rels = clique(ids[:16]) + clique(ids[16:24])
    out["S3_isolated_critical"] = ScenarioSpec(id="e1_S3_isolated_critical",
                                               description="critical population with no Connection to the infected zone",
                                               nodes=nodes, relations=rels, **base)
    # S4 redundant pathway: S2 plus one Channel from zone 1 to zone 2
    s2 = out["S2_segmented"]
    out["S4_redundant_channel"] = dataclasses.replace(
        s2, id="e1_S4_redundant_channel",
        description="S2 plus a Channel from h03 to h10 across the segmentation",
        relations=s2.relations + [chan("h03", "h10")])
    return out


# ---------------------------------------------------------- Experiment 2 ----

def exp2_specs(interval: int = 4, canary: int = 2, n_agents: int = 20) -> Dict[str, ScenarioSpec]:
    agents = [f"a{i:02d}" for i in range(n_agents)]
    nodes = [N("vendor", "vendor", I=True, vis=False, state="content")] + \
            [N(a, zones=[i + 1], state="sensor") for i, a in enumerate(agents)]
    rels = [cpd("vendor", a, "upd") for a in agents]
    base = dict(governance=GOV, nodes=nodes, relations=rels, entry_node="vendor",
                deterministic=True, rates=RATES, seed=2)
    t1 = ScenarioSpec(id="e2_T1_immediate", description="push to whole population in one step",
                      time=TimeSpec(latency_steps=2, max_steps=40), **base)
    t2 = ScenarioSpec(id="e2_T2_staged", description=f"canary {canary} agents, interval {interval}",
                      time=TimeSpec(latency_steps=2, max_steps=40,
                                    rollout={"upd": {"canary": agents[:canary], "interval": interval}}),
                      **base)
    return {"T1_immediate": t1, "T2_staged": t2}


# ---------------------------------------------------------- Experiment 3 ----

EXP3_RATES = RateSpec(threat_capability=1.0, authority_rate=0.8, execution_rate=0.8,
                      beta_conn=0.5, dependency_factor=0.35, control_plane_takeover_rate=0.0)


def exp3_specs(theta: float = 0.02, n_agents: int = 3, n_dep: int = 4) -> Dict[str, ScenarioSpec]:
    nodes = [N("vendor", "vendor", I=True, vis=False, state="build")]
    rels = []
    for i in range(n_agents):
        ag = f"agent{i}"
        nodes.append(N(ag, zones=[i + 1], state="pipeline"))
        rels.append(cpd("vendor", ag, "upd"))
        for k in range(n_dep):
            d = f"svc{i}{k}"
            nodes.append(N(d, zones=[i + 1], state="records"))
            rels.append(chan(ag, d))
    base = dict(governance=GOV, nodes=nodes, relations=rels, entry_node="vendor",
                entry_certain=True, deterministic=False, rates=EXP3_RATES, seed=3,
                time=TimeSpec(latency_steps=2, max_steps=40, exfil_dwell_steps=0))
    open_loop = ScenarioSpec(id="e3_open_loop", description="observation recorded, u(t)=0",
                             ablation=AblationSpec(True, True, False),
                             adaptation=AdaptationSpec(threshold=theta), **base)
    rem_only = ScenarioSpec(id="e3_closed_remediate_only",
                            description=f"remediate observed nodes when o(t) > {theta}",
                            ablation=AblationSpec(True, True, True),
                            adaptation=AdaptationSpec(threshold=theta), **base)
    closed = ScenarioSpec(id="e3_closed_loop",
                          description=f"remediate and revoke trust when o(t) > {theta}",
                          ablation=AblationSpec(True, True, True),
                          adaptation=AdaptationSpec(threshold=theta, actions_allowed=[
                              DefenderActionKind.REMEDIATE, DefenderActionKind.REVOKE_TRUST]),
                          **base)
    return {"open_loop": open_loop, "closed_remediate_only": rem_only, "closed_loop": closed}


# ------------------------------------------------------------- running ----

def with_model(spec: ScenarioSpec, model: str, keep_adaptation_flag=False) -> ScenarioSpec:
    """Apply an ablation model. For Experiment 3 the open-loop condition is
    itself an A ablation, so the model's A flag is ANDed with the condition's."""
    ab = MODELS[model]
    if keep_adaptation_flag:
        ab = AblationSpec(ab.structure, ab.time, ab.adaptation and spec.ablation.adaptation)
    return dataclasses.replace(spec, ablation=ab)


def run_exp1(model: str) -> Dict:
    specs = exp1_specs()
    reached = {k: set(run_scenario(with_model(s, model))[0]["reached_set"]) for k, s in specs.items()}
    return {"reached": {k: sorted(v) for k, v in reached.items()},
            "extent": {k: len(v) for k, v in reached.items()},
            "signature": reached["S1_flat"] != reached["S2_segmented"]}


def run_exp2(model: str, intervals=(0, 1, 2, 3, 4, 6, 8)) -> Dict:
    specs = exp2_specs()
    res = {k: run_scenario(with_model(s, model))[0] for k, s in specs.items()}
    frac = {k: r["frac_reached_before_observation"] for k, r in res.items()}
    first = {k: r["first_observed_step"] for k, r in res.items()}
    sweep = []
    for iv in intervals:
        s = exp2_specs(interval=iv)["T2_staged"]
        r = run_scenario(with_model(s, model))[0]
        sweep.append((iv, r["frac_reached_before_observation"], r["first_observed_step"]))
    return {"frac_before_obs": frac, "first_observed_step": first, "sweep": sweep,
            "signature": frac["T2_staged"] < frac["T1_immediate"]}


def run_exp3(model: str, n_seeds: int = 30) -> Dict:
    specs = exp3_specs()
    est = [n.id for n in specs["open_loop"].nodes if n.governance == "estate"]
    ext, rem, rev = {}, {}, {}
    for k, s in specs.items():
        s2 = with_model(s, model, keep_adaptation_flag=True)
        rows = [run_scenario(s2, n_trials=1, seed=100 + i)[0] for i in range(n_seeds)]
        ext[k] = np.array([len([n for n in r["reached_set"] if n in est]) / len(est) for r in rows])
        rem[k] = np.array([r["n_remediations"] for r in rows])
        rev[k] = np.array([len(r["revocations"]) for r in rows])
    diff = ext["open_loop"] - ext["closed_loop"]
    diff_rem = ext["open_loop"] - ext["closed_remediate_only"]
    return {"mean_extent": {k: float(v.mean()) for k, v in ext.items()},
            "median_paired_diff": float(np.median(diff)),
            "frac_seeds_closed_lower": float((diff > 0).mean()),
            "median_paired_diff_remediate_only": float(np.median(diff_rem)),
            "mean_remediations": {k: float(v.mean()) for k, v in rem.items()},
            "mean_revocations": {k: float(v.mean()) for k, v in rev.items()},
            "signature": bool(np.median(diff) > 0 and (diff > 0).mean() > 0.5)}


# --------------------------------------------------------------- tables ----

def write_outputs(results: Dict, n_seeds: int) -> None:
    os.makedirs(RES, exist_ok=True)
    md, tex = [], []
    # Experiment 1
    e1 = results["STA"]["exp1"]
    md += ["## Experiment 1, Structure (M_STA, deterministic)", "",
           "| Condition | Nodes reached (of 24) |", "|---|---|"]
    md += [f"| {k} | {v} |" for k, v in e1["extent"].items()]
    md += ["", f"Signature (reached set differs, S1 vs S2): {e1['signature']}", ""]
    # Experiment 2
    e2 = results["STA"]["exp2"]
    md += ["## Experiment 2, Time (M_STA, deterministic, latency 2)", "",
           "| Condition | Fraction reached before first observation | First observation step |", "|---|---|---|"]
    md += [f"| {k} | {e2['frac_before_obs'][k]:.2f} | {e2['first_observed_step'][k]} |" for k in e2["frac_before_obs"]]
    md += ["", "Temporal ablation (T2, interval sweep):", "", "| Interval | Fraction before observation | First observation step |", "|---|---|---|"]
    md += [f"| {iv} | {f:.2f} | {fo} |" for iv, f, fo in e2["sweep"]]
    md += ["", f"Signature (T2 < T1): {e2['signature']}", ""]
    # Experiment 3
    e3 = results["STA"]["exp3"]
    md += [f"## Experiment 3, Adaptation (M_STA, stochastic, {n_seeds} paired seeds)", "",
           "| Condition | Mean final extent | Mean remediations | Mean revocations |", "|---|---|---|---|"]
    md += [f"| {k} | {e3['mean_extent'][k]:.3f} | {e3['mean_remediations'][k]:.1f} | {e3['mean_revocations'][k]:.1f} |" for k in e3["mean_extent"]]
    md += ["", f"Median paired difference (open - closed, revoke trust): {e3['median_paired_diff']:.3f}; "
           f"closed lower in {e3['frac_seeds_closed_lower']:.0%} of seeds. Signature: {e3['signature']}",
           f"Median paired difference (open - closed, remediation only): {e3['median_paired_diff_remediate_only']:.3f} "
           "(secondary: state restoration alone under a persistent trusted source)", ""]
    # Ablation matrix
    md += ["## Ablation matrix: signature present?", "", "| Model | Structure | Time | Adaptation |", "|---|---|---|---|"]
    for m in MODELS:
        r = results[m]
        md += [f"| M_{m} | {r['exp1']['signature']} | {r['exp2']['signature']} | {r['exp3']['signature']} |"]
    h4 = all(results["STA"][e]["signature"] for e in ("exp1", "exp2", "exp3"))
    h5 = (not results["TA"]["exp1"]["signature"]) and (not results["SA"]["exp2"]["signature"]) \
        and (not results["ST"]["exp3"]["signature"])
    md += ["", f"H4 (all three signatures present under M_STA): {h4}",
           f"H5 (each dimension's removal loses its signature: TA/Structure, SA/Time, ST/Adaptation): {h5}"]
    with open(os.path.join(RES, "archetype_results.md"), "w") as f:
        f.write("\n".join(md) + "\n")

    # LaTeX ablation matrix
    tick = lambda b: "\\checkmark" if b else "$\\times$"
    tex += ["% Generated by experiments.archetypes; do not edit by hand.",
            "\\begin{table}[t]",
            "\\caption{Ablation matrix: whether each intervention signature is present under each representation. "
            "Structure: reached set differs between S1 and S2. Time: fraction reached before first observation is lower "
            "under staged than immediate rollout. Adaptation: closed-loop extent is lower than open-loop over paired seeds.}",
            "\\label{tab:ablation}", "\\centering", "\\begin{tabular}{lccc}", "\\toprule",
            "Model & Structure & Time & Adaptation \\\\", "\\midrule"]
    for m in MODELS:
        r = results[m]
        tex.append(f"$M_{{{m}}}$ & {tick(r['exp1']['signature'])} & {tick(r['exp2']['signature'])} & {tick(r['exp3']['signature'])} \\\\")
    tex += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
    with open(os.path.join(RES, "ablation_matrix.tex"), "w") as f:
        f.write("\n".join(tex) + "\n")

    with open(os.path.join(RES, "archetype_results.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["model", "exp1_S1", "exp1_S2", "exp1_S3", "exp1_S4", "exp1_sig",
                    "exp2_T1_frac", "exp2_T2_frac", "exp2_sig",
                    "exp3_open_extent", "exp3_closed_extent", "exp3_median_diff", "exp3_sig"])
        for m, r in results.items():
            w.writerow([m, *[r["exp1"]["extent"][k] for k in ("S1_flat", "S2_segmented", "S3_isolated_critical", "S4_redundant_channel")],
                        r["exp1"]["signature"],
                        f"{r['exp2']['frac_before_obs']['T1_immediate']:.3f}", f"{r['exp2']['frac_before_obs']['T2_staged']:.3f}", r["exp2"]["signature"],
                        f"{r['exp3']['mean_extent']['open_loop']:.3f}", f"{r['exp3']['mean_extent']['closed_loop']:.3f}",
                        f"{r['exp3']['median_paired_diff']:.3f}", r["exp3"]["signature"]])
    print("\n".join(md))
    print(f"\nwritten -> {RES}")


def write_specs() -> None:
    os.makedirs(OUT, exist_ok=True)
    for group in (exp1_specs(), exp2_specs(), exp3_specs()):
        for s in group.values():
            problems = s.validate()
            if problems:
                raise SystemExit(f"{s.id}: {problems}")
            dump_spec(s, os.path.join(OUT, f"{s.id}.yaml"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=30)
    a = ap.parse_args()
    write_specs()
    results = {}
    for m in MODELS:
        print(f"model {m} ...", flush=True)
        results[m] = {"exp1": run_exp1(m), "exp2": run_exp2(m), "exp3": run_exp3(m, a.seeds)}
    write_outputs(results, a.seeds)


if __name__ == "__main__":
    main()
