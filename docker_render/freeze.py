"""
Freeze and verify the correspondence set.

  python -m docker_render.freeze            write FREEZE.md and freeze.json
  python -m docker_render.freeze --verify   check the tree against freeze.json

What is frozen: every file in cemt_core/, docker_render/node_service.py,
docker_render/probe.py, docker_render/render.py, every scenario YAML in
scenarios/tier1/ and the manifest. The record carries the core version, the
git commit if available, the timestamp and a SHA-256 per file plus one
digest over all of them.

A tier 1 run made after the freeze is a pre-registered evaluation only if
`--verify` passes at the time of the run; tier1_set records the digest it
ran against in tier1_run_record.json for that reason.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FROZEN_DIRS = ["cemt_core", os.path.join("scenarios", "tier1")]
FROZEN_FILES = [os.path.join("docker_render", f) for f in
                ("node_service.py", "probe.py", "render.py")]
EXCLUDE = {"__pycache__", "tier1_results.csv", "tier1_results.md",
           "tier1_results.tex", "tier1_run_record.json"}


def _sha(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read().replace(b"\r\n", b"\n"))   # line-ending independent
    return h.hexdigest()


def frozen_paths():
    out = []
    for d in FROZEN_DIRS:
        for root, dirs, files in os.walk(os.path.join(ROOT, d)):
            dirs[:] = [x for x in dirs if x not in EXCLUDE]
            for f in sorted(files):
                if f in EXCLUDE or f.endswith(".pyc"):
                    continue
                out.append(os.path.relpath(os.path.join(root, f), ROOT))
    out += FROZEN_FILES
    return sorted(set(p.replace("\\", "/") for p in out))


def build_record() -> dict:
    sys.path.insert(0, ROOT)
    from cemt_core import CORE_VERSION
    files = {p: _sha(os.path.join(ROOT, p)) for p in frozen_paths()}
    digest = hashlib.sha256("".join(f"{k}:{v}\n" for k, v in sorted(files.items())).encode()).hexdigest()
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                         stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = "not in a git checkout"
    return {"core_version": CORE_VERSION, "git_commit": commit,
            "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "set_digest": digest, "n_scenarios": sum(1 for p in files if p.endswith(".yaml") and "tier1" in p and "manifest" not in p),
            "files": files}


def write(record: dict) -> None:
    with open(os.path.join(ROOT, "freeze.json"), "w") as f:
        json.dump(record, f, indent=2)
    lines = ["# FREEZE record", "",
             f"- core version: {record['core_version']}",
             f"- git commit: {record['git_commit']}",
             f"- frozen at: {record['frozen_at']}",
             f"- scenarios: {record['n_scenarios']}",
             f"- set digest (SHA-256 over all frozen files): `{record['set_digest']}`", "",
             "Any change to a frozen file after this record is a model or scenario",
             "revision and requires a new record. Verify with",
             "`python -m docker_render.freeze --verify`.", "",
             "| File | SHA-256 |", "|---|---|"]
    lines += [f"| {k} | `{v[:16]}…` |" for k, v in sorted(record["files"].items())]
    with open(os.path.join(ROOT, "FREEZE.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def verify() -> bool:
    path = os.path.join(ROOT, "freeze.json")
    if not os.path.exists(path):
        print("no freeze.json; run without --verify first")
        return False
    with open(path) as f:
        rec = json.load(f)
    now = build_record()
    changed = [p for p in set(rec["files"]) | set(now["files"])
               if rec["files"].get(p) != now["files"].get(p)]
    if changed:
        print("FROZEN SET MODIFIED since", rec["frozen_at"])
        for p in sorted(changed):
            print("  ", p)
        return False
    print(f"frozen set intact: digest {rec['set_digest'][:16]}… ({rec['n_scenarios']} scenarios, {rec['core_version']})")
    return True


def current_digest() -> str | None:
    path = os.path.join(ROOT, "freeze.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        rec = json.load(f)
    return rec["set_digest"] if verify_quiet(rec) else None


def verify_quiet(rec: dict) -> bool:
    now = build_record()
    return all(rec["files"].get(p) == now["files"].get(p)
               for p in set(rec["files"]) | set(now["files"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if a.verify:
        sys.exit(0 if verify() else 1)
    rec = build_record()
    write(rec)
    print(f"frozen: {rec['n_scenarios']} scenarios, {rec['core_version']}, "
          f"digest {rec['set_digest'][:16]}…  -> FREEZE.md, freeze.json")


if __name__ == "__main__":
    main()
