"""
Render a ScenarioSpec to the Docker micro-system.

  node_envs(spec)          -> {node_id: {ENV: value}}   (shared with the local harness)
  write_bundle(spec, dir)  -> writes compose.yaml, Dockerfile, node_service.py,
                              spec.yaml into `dir`

Network realisation
  zone-<z>       one bridge network per zone; a node joins the networks of its
                 zones, so connection reachability is physical, not configured
  grp-<group>    one network per directing control plane (controller plus
                 members) and per conferring plane (issuer plus members)
  route          one network for all channel edges
  observer       the probe's network, joined by every node

Tokens make channel and control-plane membership real: a member accepts a
channel push only with the root's token, and a plane push only with the
controller's token. Conferral is therefore an artefact of holding the token,
which is what compromise of the root or controller yields.
"""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from typing import Dict, List

import yaml

from cemt_core.spec import Condition, RelationClass, ScenarioSpec

HERE = os.path.dirname(os.path.abspath(__file__))


def node_envs(spec: ScenarioSpec, addrs: Dict[str, str] | None = None) -> Dict[str, Dict[str, str]]:
    peers: Dict[str, set] = defaultdict(set)
    x_sup: Dict[str, set] = defaultdict(set)
    a_sup: Dict[str, set] = defaultdict(set)
    cp_ctl: Dict[str, str] = {}
    cp_members: Dict[str, List[str]] = defaultdict(list)
    ch_down: Dict[str, List[str]] = defaultdict(list)

    for r in spec.relations:
        if r.relation_class == RelationClass.CONNECTION:
            peers[r.supplier].add(r.receiver)
            peers[r.receiver].add(r.supplier)          # symmetric adjacency
        elif r.relation_class == RelationClass.CHANNEL:
            ch_down[r.supplier].append(r.receiver)
            x_sup[r.receiver].add(r.supplier)          # standing X supply
        elif r.relation_class == RelationClass.CONTROL_PLANE_DIRECTING:
            g = r.group or f"cpd-{r.supplier}"
            cp_ctl[g] = r.supplier
            cp_members[g].append(r.receiver)           # supplies admission
        elif r.relation_class == RelationClass.CONTROL_PLANE_CONFERRING:
            a_sup[r.receiver].add(r.supplier)          # standing A supply

    member_cp_tokens: Dict[str, List[str]] = defaultdict(list)
    for g, mem in cp_members.items():
        for m in mem:
            member_cp_tokens[m].append(f"tok-{g}")

    ctl_of: Dict[str, str] = {ctl: g for g, ctl in cp_ctl.items()}

    envs: Dict[str, Dict[str, str]] = {}
    for n in spec.nodes:
        e = {
            "NODE_ID": n.id,
            "INTERFACE": "1" if n.interface else "0",
            "EXEC_PATHWAY": "1" if n.execution_pathway else "0",
            "AUTHORITY": "1" if n.authority else "0",
            "STATE_OBJECT": n.state_object,
            "X_SUPPLIERS": ",".join(sorted(x_sup[n.id])),
            "A_SUPPLIERS": ",".join(sorted(a_sup[n.id])),
            "CONN_PEERS": ",".join(sorted(peers[n.id])),
            "CHANNEL_DOWNSTREAM": ",".join(sorted(ch_down[n.id])),
            "CP_MEMBER_TOKENS": ",".join(member_cp_tokens[n.id]),
        }
        if n.id in ctl_of:
            g = ctl_of[n.id]
            e["CP_GROUP"] = g
            e["CP_MEMBERS"] = ",".join(sorted(cp_members[g]))
            e["CP_TOKEN"] = f"tok-{g}"
        if addrs:
            e["ADDRS"] = ",".join(f"{k}={v}" for k, v in addrs.items())
        envs[n.id] = e
    return envs


def compose_dict(spec: ScenarioSpec) -> Dict:
    envs = node_envs(spec)
    networks = {"observer": {}, "route": {}}
    services: Dict[str, Dict] = {}
    for n in spec.nodes:
        nets = ["observer"]
        for z in n.zones:
            nets.append(f"zone-{z}")
            networks[f"zone-{z}"] = {}
        services[n.id] = {
            "image": "cemt-node",
            "container_name": f"cemt-{spec.id}-{n.id}",
            "hostname": n.id,
            "environment": envs[n.id],
            "networks": nets,
        }
    for r in spec.relations:
        if r.relation_class in (RelationClass.CONTROL_PLANE_DIRECTING,
                                RelationClass.CONTROL_PLANE_CONFERRING):
            g = f"grp-{r.group or r.supplier}"
            networks[g] = {}
            for side in (r.supplier, r.receiver):
                if g not in services[side]["networks"]:
                    services[side]["networks"].append(g)
        elif r.relation_class == RelationClass.CHANNEL:
            for side in (r.supplier, r.receiver):
                if "route" not in services[side]["networks"]:
                    services[side]["networks"].append("route")
    services["probe"] = {
        "image": "cemt-node",
        "container_name": f"cemt-{spec.id}-probe",
        "command": ["python", "probe.py", "/app/spec.yaml", "--out", "/app/out/probe.json"],
        "volumes": ["./out:/app/out"],
        "networks": ["observer"],
        "depends_on": [n.id for n in spec.nodes],
    }
    return {"services": services, "networks": networks}


DOCKERFILE = """FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir pyyaml
COPY node_service.py probe.py spec.yaml ./
COPY cemt_core ./cemt_core
CMD ["python", "node_service.py"]
"""


def write_bundle(spec: ScenarioSpec, out_dir: str, cemt_core_dir: str | None = None) -> str:
    os.makedirs(os.path.join(out_dir, "out"), exist_ok=True)
    with open(os.path.join(out_dir, "compose.yaml"), "w") as f:
        yaml.safe_dump(compose_dict(spec), f, sort_keys=False)
    with open(os.path.join(out_dir, "Dockerfile"), "w") as f:
        f.write(DOCKERFILE)
    shutil.copy(os.path.join(HERE, "node_service.py"), out_dir)
    shutil.copy(os.path.join(HERE, "probe.py"), out_dir)
    from cemt_core.spec import dump_spec
    dump_spec(spec, os.path.join(out_dir, "spec.yaml"))
    src = cemt_core_dir or os.path.join(os.path.dirname(HERE), "cemt_core")
    dst = os.path.join(out_dir, "cemt_core")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return out_dir


if __name__ == "__main__":
    import argparse
    from cemt_core.spec import load_spec
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = write_bundle(load_spec(a.spec), a.out)
    print(f"bundle written to {d}\n  cd {d}\n  docker build -t cemt-node .\n  docker compose up --abort-on-container-exit probe")
