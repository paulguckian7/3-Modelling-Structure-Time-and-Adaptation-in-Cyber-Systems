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

import json
import subprocess

from .local_harness import run_local
from .render import write_bundle

HERE = os.path.dirname(os.path.abspath(__file__))
T1 = os.path.join(os.path.dirname(HERE), "scenarios", "tier1")


# ---------------------------------------------------------------- docker ----

def _compose(bundle, *args, timeout=600):
    return subprocess.run(["docker", "compose", *args], cwd=bundle, check=True,
                          timeout=timeout, capture_output=True, text=True)


def run_docker(spec_path: str, runs_dir: str, removed: str | None = None) -> dict:
    """Same contract as run_local, executed against the compose bundle.
    Fresh containers for every run so state never carries over."""
    from cemt_core.spec import load_spec
    spec = load_spec(spec_path)
    if removed == spec.entry_node:
        raise ValueError("cannot remove the entry node")
    bundle = os.path.join(runs_dir, spec.id)
    write_bundle(spec, bundle)
    out = os.path.join(bundle, "out")
    os.makedirs(out, exist_ok=True)
    tag = f"probe_{removed}.json" if removed else "probe.json"
    for f in os.listdir(out):
        if f == tag:
            os.remove(os.path.join(out, f))
    try:
        subprocess.run(["docker", "build", "-q", "-t", "cemt-node", "."], cwd=bundle,
                       check=True, timeout=900, capture_output=True, text=True)
        _compose(bundle, "up", "-d", "--remove-orphans")
        if removed:
            _compose(bundle, "stop", removed)
        cmd = ["run", "--rm", "--no-deps", "probe", "python", "probe.py", "/app/spec.yaml",
               "--out", f"/app/out/{tag}"]
        if removed:
            cmd += ["--removed", removed]
        try:
            _compose(bundle, *cmd)
        except subprocess.CalledProcessError as e:
            # probe exits 1 on a mismatch, which is a result, not an error
            if not os.path.exists(os.path.join(out, tag)):
                raise RuntimeError(f"probe failed: {e.stderr[-2000:]}")
    finally:
        try:
            _compose(bundle, "down", "--remove-orphans", timeout=300)
        except Exception:
            pass
    with open(os.path.join(out, tag)) as f:
        r = json.load(f)
    r["removed"] = removed
    return r



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


def run_set(only=None, verbose=False, mode="local_harness", runs_dir=None):
    with open(os.path.join(T1, "manifest.yaml")) as f:
        manifest = yaml.safe_load(f)
    if mode == "docker":
        runner = lambda p, removed=None: run_docker(p, runs_dir, removed)
    else:
        runner = lambda p, removed=None: run_local(p, removed)
    rows = []
    for sid, m in manifest.items():
        if only and sid not in only:
            continue
        path = os.path.join(T1, m["file"])
        t0 = time.time()
        r = runner(path)
        obs_v = check_expectations(r["observed"], m)
        pred_v = check_expectations(r["predicted"], m)
        cut_ok, cut_notes = True, []
        for sup, receivers in m["cut_removals"].items():
            rr = runner(path, removed=sup)
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


def write_run_record(rows, mode="local_harness"):
    import json, datetime as dt
    from .freeze import current_digest
    from cemt_core import CORE_VERSION
    digest = current_digest()
    rec = {"core_version": CORE_VERSION,
           "run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "mode": mode,
           "frozen_set_digest": digest,
           "pre_registered": digest is not None,
           "n_pass": int(sum(r["pass"] for r in rows)), "n": len(rows),
           "rows": rows}
    with open(os.path.join(T1, "tier1_run_record.json"), "w") as f:
        json.dump(rec, f, indent=2)
    tag = "PRE-REGISTERED (frozen set verified)" if digest else \
          "DEVELOPMENT (no freeze record or frozen set modified)"
    print(f"run record -> tier1_run_record.json  [{tag}]")


def write_table(rows, mode="local_harness"):
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
    write_latex(rows, mode)
    print(f"\n{n_pass}/{len(rows)} pass. Table -> {os.path.join(T1, 'tier1_results.md')}")
    return n_pass == len(rows)


# Short, paper-facing claim per scenario and the Table 1 row it exercises.
_TEX_CLAIMS = {
    "c01_connection_chain":         ("I",    "Connection chain; one hop per step"),
    "c02_zone_isolation":           ("I",    "No relation across zones (negative control)"),
    "c03_no_interface":             ("I",    "No admission relation at all (negative control)"),
    "c04_no_execution_pathway":     ("X",    "Execution Pathway absent, no supplier (negative control)"),
    "c05_no_authority":             ("A",    "Authority absent, no supplier (negative control)"),
    "c06_directing_external_trust": ("A",    "Directing External Trust from a vendor; non-member untouched"),
    "c07_directing_needs_local_x":  ("A",    "Directed member without local route not reached (negative control)"),
    "c08_conferring_control_plane": ("A",    "Conferring issuer supplies A; admits nothing"),
    "c09_cp_timing":                ("A",    "Ownership one step after activation, push one step later"),
    "c10_channel_route_cascade":    ("X",    "Compromise along a channel route"),
    "c11_channel_cut":              ("X",    "Cut: sole channel supplier removed"),
    "c12_connection_cut":           ("I",    "Cut: sole admitting neighbour removed"),
    "c13_conferring_cut":           ("A",    "Cut: sole conferring issuer removed"),
    "c14_directing_cut":            ("A",    "Cut: sole directing controller removed"),
    "c15_fanout":                   ("I",    "Fan-out six, all reached in one step"),
    "c16_boundary_not_crossed":     ("A",    "Vendor has no inbound relation (negative control)"),
    "c17_two_planes":               ("A",    "Two directing planes chained through a shared member"),
    "c18_micro_01_mixed":           ("all",  "All classes together (micro-system 01)"),
    "c19_cycle":                    ("X",    "Cyclic routes; run terminates"),
    "c20_static_x_supply":          ("X",    "Standing supply from a healthy upstream; Cut still holds"),
}


def _tex(s):
    return str(s).replace("_", "\\_").replace("&", "\\&")


def write_latex(rows, mode="local_harness"):
    lines = [
        "% Generated by docker_render.tier1_set; do not edit by hand.",
        "\\begin{table*}[t]",
        "\\caption{Tier 1 structural correspondence: the pre-registered scenario set. "
        "Row: the Table~1 row of Paper~1B exercised. Exact: the reached set, reach steps and "
        "plane ownership observed in the executable micro-system equal the model's "
        "deterministic trace. Theory: both worlds satisfy the expectations fixed in the "
        "manifest before either was run. Cut: for each declared Cut, removing the supplying "
        "node makes the receivers unreachable in both worlds.}",
        "\\label{tab:tier1}",
        "\\centering",
        "\\begin{tabular}{llp{7.2cm}ccc}",
        "\\toprule",
        "Scenario & Row & Claim & Exact & Theory & Cut \\\\",
        "\\midrule",
    ]
    for r in rows:
        row, claim = _TEX_CLAIMS.get(r["scenario"], ("", r["claim"]))
        theory = "\\checkmark" if (r["theory_obs"] == "ok" and r["theory_model"] == "ok") else "$\\times$"
        exact = "\\checkmark" if r["exact"] else "$\\times$"
        if r["cuts"] == "-":
            cut = "--"
        else:
            cut = "\\checkmark" if "FAIL" not in r["cuts"] else "$\\times$"
        lines.append(f"{_tex(r['scenario'])} & {row} & {_tex(claim)} & {exact} & {theory} & {cut} \\\\")
    n_pass = sum(r["pass"] for r in rows)
    lines += ["\\bottomrule", "\\end{tabular}",
              f"\\vspace{{2pt}}\\par\\footnotesize {n_pass}/{len(rows)} scenarios pass all three criteria. "
              "Micro-system observations: local process harness; Docker run pending.",
              "\\end{table*}"]
    with open(os.path.join(T1, "tier1_results.tex"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"LaTeX table -> {os.path.join(T1, 'tier1_results.tex')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--docker", action="store_true", help="run under Docker Compose")
    ap.add_argument("--runs-dir", default=None,
                    help="bundle directory for --docker (keep outside OneDrive)")
    a = ap.parse_args()
    mode = "docker" if a.docker else "local_harness"
    if a.docker and not a.runs_dir:
        ap.error("--docker requires --runs-dir")
    rows = run_set(only=a.only, mode=mode, runs_dir=a.runs_dir)
    ok = write_table(rows, mode)
    write_run_record(rows, mode)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
