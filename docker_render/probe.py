#!/usr/bin/env python3
"""
Correspondence probe (tier 1, structural, exact).

Drives the micro-system in rounds that correspond one-to-one with model
steps, observes each node's state through /status, and compares the
observed trace with the Python model's deterministic trace for the same
spec. Runs inside the compose bundle (hostnames) or against the local
harness (127.0.0.1:port address book).

Round protocol
  round 0   POST entry /deliver/entry
  round k   for every node compromised at a step < k, POST /act {step: k}
            (order: nodes sorted by compromise step, then id, so the trace
            is reproducible); then read every /status
  stop      when a round produces no new compromise and no node acted, or
            max_rounds is reached

Output: JSON with observed and predicted traces and an exact-match verdict.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# bypass any system proxy: all traffic is container-to-container or localhost
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
from typing import Dict, List, Optional, Tuple


def _http(method, base, path, body=None, timeout=5.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"http://{base}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with _OPENER.open(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception:
        return None, {}


def wait_ready(addrs: Dict[str, str], timeout=60.0) -> List[str]:
    t0 = time.time()
    missing = set(addrs)
    while missing and time.time() - t0 < timeout:
        for n in list(missing):
            s, _ = _http("GET", addrs[n], "/status")
            if s == 200:
                missing.discard(n)
        if missing:
            time.sleep(0.3)
    return sorted(missing)


def observe(addrs: Dict[str, str]) -> Dict[str, Dict]:
    out = {}
    for n, a in addrs.items():
        s, st = _http("GET", a, "/status")
        if s == 200:
            out[n] = st
    return out


def drive(addrs: Dict[str, str], entry: str, max_rounds: int = 50,
          log=None) -> Dict:
    t0 = time.time()
    def _log(msg):
        if log:
            log(f"[probe +{time.time()-t0:5.1f}s] {msg}")
    s, r = _http("POST", addrs[entry], "/deliver/entry",
                 {"step": 0, "payload": "initial-payload"})
    _log(f"entry {entry}: {s} {r}")
    if s != 201:
        return {"error": f"entry failed at {entry}: {s} {r}", "reached": [],
                "planes_owned": [], "rounds": 0}

    for k in range(1, max_rounds + 1):
        st = observe(addrs)
        actors = sorted((n for n, v in st.items()
                         if v["compromised"] and v["step"] is not None and v["step"] < k),
                        key=lambda n: (st[n]["step"], n))
        acted = 0
        _log(f"round {k}: actors {actors}")
        for n in actors:
            s, r = _http("POST", addrs[n], "/act", {"step": k})
            acted += int(bool(r.get("acted")))
            _log(f"  {n} act -> {s} {r.get('log', r)}")
        st_after = observe(addrs)
        new = [n for n, v in st_after.items()
               if v["compromised"] and not st.get(n, {}).get("compromised")]
        planes_before = {g for v in st.values() for g in v["planes_owned"]}
        planes_after = {g for v in st_after.values() for g in v["planes_owned"]}
        new_planes = sorted(planes_after - planes_before)
        _log(f"round {k}: new {new} planes {new_planes}")
        # quiescence: nothing changed this round, so nothing can change later
        if not new and not new_planes:
            break

    final = observe(addrs)
    reached = sorted(((v["step"], n, v["via"]) for n, v in final.items() if v["compromised"]),
                     key=lambda t: (t[0], t[1]))
    planes = sorted(((step, g, "controller") for v in final.values()
                     for g, step in v["planes_owned"].items()),
                    key=lambda t: (t[0], t[1]))
    return {"reached": [list(t) for t in reached],
            "planes_owned": [list(t) for t in planes],
            "reached_set": sorted(n for n, v in final.items() if v["compromised"]),
            "rounds": k}


def predict(spec_path: str, removed: Optional[str] = None) -> Dict:
    from cemt_core.spec import load_spec
    from cemt_core.step import run_scenario
    import dataclasses
    spec = load_spec(spec_path)
    if removed:
        spec = dataclasses.replace(
            spec,
            nodes=[n for n in spec.nodes if n.id != removed],
            relations=[r for r in spec.relations if removed not in (r.supplier, r.receiver)])
    r = run_scenario(spec)[0]
    return {"reached": [[s, n, v] for s, n, v in r["reached"]],
            "planes_owned": [list(t) for t in r["planes_owned"]],
            "reached_set": r["reached_set"],
            "entry": r["entry"]}


def compare(observed: Dict, predicted: Dict) -> Dict:
    def key(tr):   # (step, node) pairs sorted; within-step order is not a
        return sorted((t[0], t[1]) for t in tr)   # model quantity
    steps_match = key(observed["reached"]) == key(predicted["reached"])
    set_match = observed.get("reached_set") == predicted.get("reached_set")
    planes_match = observed["planes_owned"] == predicted["planes_owned"]
    via_obs = {t[1]: t[2] for t in observed["reached"]}
    via_pred = {t[1]: t[2].split("|")[0] for t in predicted["reached"]}
    via_match = all(via_obs.get(n) == via_pred.get(n) for n in via_pred)
    return {"exact_match": steps_match and set_match and planes_match,
            "reached_steps_match": steps_match, "reached_set_match": set_match,
            "planes_match": planes_match, "via_match": via_match}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--addrs", help="id=host:port,... (default: docker hostnames)")
    ap.add_argument("--out")
    ap.add_argument("--removed", help="node stopped for a Cut check")
    a = ap.parse_args()

    sys.path.insert(0, ".")
    from cemt_core.spec import load_spec
    spec = load_spec(a.spec)
    ids = [n.id for n in spec.nodes if n.id != a.removed]
    if a.addrs:
        book = dict(x.split("=", 1) for x in a.addrs.split(","))
        addrs = {n: book[n] for n in ids}
    else:
        addrs = {n: f"{n}:8000" for n in ids}

    missing = wait_ready(addrs)
    if missing:
        print(f"nodes not ready: {missing}", file=sys.stderr)
        sys.exit(2)

    entry = spec.entry_node
    observed = drive(addrs, entry, spec.time.max_steps)
    predicted = predict(a.spec, removed=a.removed)
    verdict = compare(observed, predicted)
    result = {"spec": spec.id, "removed": a.removed, "observed": observed,
              "predicted": predicted, "verdict": verdict}
    text = json.dumps(result, indent=2)
    if a.out:
        with open(a.out, "w") as f:
            f.write(text)
    print(text)
    sys.exit(0 if verdict["exact_match"] else 1)


if __name__ == "__main__":
    main()
