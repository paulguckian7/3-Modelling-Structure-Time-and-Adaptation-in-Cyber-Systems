"""
Local harness: run the micro-system as plain processes on 127.0.0.1.

Used to verify the correspondence logic without Docker. The node service
and probe are byte-identical to what runs in the containers; only the
address book differs. Network isolation (zone and group networks) is NOT
reproduced here, so the harness verifies the kill-chain and relation logic,
and the Docker run additionally verifies physical reachability.

Usage:
  python -m docker_render.local_harness scenarios/micro_01_supply_chain.yaml
  python -m docker_render.local_harness scenarios/micro_01_supply_chain.yaml --removed db-1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

from cemt_core.spec import load_spec
from . import probe
from .render import node_envs

HERE = os.path.dirname(os.path.abspath(__file__))


def run_local(spec_path: str, removed: str | None = None, base_port: int = 9100,
              verbose: bool = False) -> dict:
    spec = load_spec(spec_path)
    if removed == spec.entry_node:
        raise ValueError("cannot remove the entry node; choose a supplier")
    ids = [n.id for n in spec.nodes]
    addrs = {n: f"127.0.0.1:{base_port + i}" for i, n in enumerate(ids)}
    envs = node_envs(spec, addrs)
    procs = []
    tmp = tempfile.mkdtemp(prefix="cemt_")
    t0 = time.time()
    log = (lambda m: print(m, file=sys.stderr, flush=True)) if verbose else None
    try:
        for i, n in enumerate(ids):
            if n == removed:
                continue
            env = {**os.environ, **envs[n], "PORT": str(base_port + i),
                   "STATE_PATH": os.path.join(tmp, f"{n}.state")}
            procs.append(subprocess.Popen(
                [sys.executable, os.path.join(HERE, "node_service.py")], env=env,
                stderr=None if verbose else subprocess.DEVNULL))
        live = {n: a for n, a in addrs.items() if n != removed}
        if log: log(f"[harness +{time.time()-t0:5.1f}s] {len(procs)} services spawned, waiting")
        missing = probe.wait_ready(live, timeout=20)
        if missing:
            raise RuntimeError(f"services not ready: {missing}")
        if log: log(f"[harness +{time.time()-t0:5.1f}s] all ready, driving")
        observed = probe.drive(live, spec.entry_node, spec.time.max_steps, log=log)
        if log: log(f"[harness +{time.time()-t0:5.1f}s] observed; running model")
        predicted = probe.predict(spec_path, removed=removed)
        if log: log(f"[harness +{time.time()-t0:5.1f}s] done")
        verdict = probe.compare(observed, predicted)
        return {"spec": spec.id, "removed": removed, "observed": observed,
                "predicted": predicted, "verdict": verdict}
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=3)
            except Exception:
                p.kill()


def run_correspondence_set(spec_path: str) -> dict:
    """Tier 1 protocol for one spec: full run plus one removal run per Cut
    supplier (excluding the entry node). Returns a per-check table."""
    from cemt_core.relations import RelationTable
    spec = load_spec(spec_path)
    rt = RelationTable(spec)
    checks = [("full", None, run_local(spec_path))]
    suppliers = sorted({s for s, _, _, _ in rt.cut_table()} - {spec.entry_node})
    for sup in suppliers:
        r = run_local(spec_path, removed=sup)
        expected_lost = sorted({rcv for s, rcv, _, _ in rt.cut_table() if s == sup})
        r["cut_receivers"] = expected_lost
        r["cut_confirmed"] = all(x not in r["observed"]["reached_set"] for x in expected_lost)
        checks.append((f"remove {sup}", sup, r))
    rows = [{"check": c, "removed": s, "exact_match": r["verdict"]["exact_match"],
             "reached": r["observed"]["reached_set"],
             "cut_receivers": r.get("cut_receivers"), "cut_confirmed": r.get("cut_confirmed")}
            for c, s, r in checks]
    return {"spec": spec.id, "all_exact": all(x["exact_match"] for x in rows), "checks": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--removed")
    ap.add_argument("--set", action="store_true", help="run the full tier 1 set")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    if a.set:
        r = run_correspondence_set(a.spec)
        for row in r["checks"]:
            cut = "" if row["cut_receivers"] is None else \
                f"  cut receivers={row['cut_receivers']} confirmed={row['cut_confirmed']}"
            print(f"{row['check']:22s} exact={row['exact_match']!s:5s} reached={row['reached']}{cut}")
        print("ALL EXACT:", r["all_exact"])
        sys.exit(0 if r["all_exact"] else 1)
    r = run_local(a.spec, a.removed, verbose=a.verbose)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["verdict"]["exact_match"] else 1)


if __name__ == "__main__":
    main()
