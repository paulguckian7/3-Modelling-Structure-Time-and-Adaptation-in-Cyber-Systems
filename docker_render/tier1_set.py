"""
Tier 1 correspondence runner.

For every scenario in scenarios/tier1/manifest.yaml:
  1. run the local harness (or, with --docker-results DIR, read probe JSON
     produced by the compose bundles) to get observed and predicted traces
  2. check exact agreement between the two worlds
  3. check BOTH worlds against the manifest's theory expectations
  4. run each cut removal and check the receivers drop out in both worlds

Writes scenarios/tier1/tier1_results.csv and tier1_results.md.

Run:  python -m docker_render.tier1_set
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time

import yaml

from .local_harness import run_local

HERE = os.path.dirname(os.path.abspath(__file__))
T1 = os.path.join(os.path.dirname(HERE), "scenarios", "tier1")


def check_expectations(trace: dict, exp: dict) -> list:
    """Return a list of violations of the manifest for one trace."""
    reached = set(trace["reached_set"])
    steps = {n: s for s, n, _ in trace["reached"]}
    v = []
    for n in exp["must_reach"]:
        if n not in reached:
            v.append(f"{n} not reached")
    for n in exp["must_not_reach"]:
        if n in reached:
            v.append(f"{n} reached")
    for n, s in exp["reach_step"].items():
        if steps.get(n) != s:
            v.append(f"{n} step {steps.get(n)} != {s}")
    return v


def run_set(only=None, verbose=False):
    with open(os.path.join(T1, "manifest.yaml")) as f:
        manifest = yaml.safe_load(f)
    rows = []
    for sid, m in manifest.items():
        if only and sid not in only:
            continue
        path = os.path.join(T1, m["file"])
        t0 = time.time()
        r = run_local(path)
        obs_v = check_expectations(r["observed"], m)
        pred_v = check_expectations(r["predicted"], m)
        cut_ok, cut_notes = True, []
        for sup, receivers in m["cut_removals"].items():
            rr = run_local(path, removed=sup)
            still_obs = [x for x in receivers if x in rr["observed"]["reached_set"]]
            still_pred = [x for x in receivers if x in rr["predicted"]["reached_set"]]
            ok = rr["verdict"]["exact_match"] and not still_obs and not still_pred
            cut_ok &= ok
            cut_notes.append(f"-{sup}:{'ok' if ok else 'FAIL'}")
        row = {
            "scenario": sid,
            "claim": m["claim"],
            "n_nodes": len(r["predicted"]["reached_set"]) + len(m["must_not_reach"]),
            "reached": len(r["observed"]["reached_set"]),
            "exact": r["verdict"]["exact_match"],
            "theory_obs": "ok" if not obs_v else "; ".join(obs_v),
            "theory_model": "ok" if not pred_v else "; ".join(pred_v),
            "cuts": " ".join(cut_notes) if cut_notes else "-",
            "pass": r["verdict"]["exact_match"] and not obs_v and not pred_v and cut_ok,
            "secs": round(time.time() - t0, 1),
        }
        rows.append(row)
        print(f"{sid:28s} exact={row['exact']!s:5s} theory(obs)={row['theory_obs']:6s} "
              f"theory(model)={row['theory_model']:6s} cuts={row['cuts']:14s} "
              f"{'PASS' if row['pass'] else 'FAIL'}  ({row['secs']}s)", flush=True)
    return rows


def write_table(rows):
    with open(os.path.join(T1, "tier1_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    lines = ["| Scenario | Claim | Exact | Theory (obs) | Theory (model) | Cuts | Pass |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['scenario']} | {r['claim']} | {r['exact']} | {r['theory_obs']} | "
                     f"{r['theory_model']} | {r['cuts']} | {'yes' if r['pass'] else 'NO'} |")
    n_pass = sum(r["pass"] for r in rows)
    lines.append(f"\n{n_pass}/{len(rows)} scenarios pass.")
    with open(os.path.join(T1, "tier1_results.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\n{n_pass}/{len(rows)} pass. Table -> {os.path.join(T1, 'tier1_results.md')}")
    return n_pass == len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    rows = run_set(only=a.only)
    ok = write_table(rows)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
