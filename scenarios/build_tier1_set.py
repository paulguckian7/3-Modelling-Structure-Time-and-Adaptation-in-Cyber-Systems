"""
Build the tier 1 correspondence scenario set (Paper 3A).

Writes scenarios/tier1/c01_*.yaml ... and scenarios/tier1/manifest.yaml.

Each scenario isolates one structural claim from Papers 1A, 1B or 2. The
manifest records, per scenario, the expectations the THEORY fixes before
either implementation is run:
  must_reach     nodes that must be compromised
  must_not_reach nodes that must remain healthy (negative controls)
  reach_step     exact step for selected nodes (timing claims)
  cut_removals   supplier -> receivers that must drop out when the supplier
                 is removed (Paper 1B Cut)
The harness then checks (a) both worlds agree exactly and (b) both satisfy
the manifest. A pass on (a) alone would only show the two implementations
share an error.

Run:  python scenarios/build_tier1_set.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yaml

from cemt_core.spec import (Condition, Governance, Node, Relation, RelationClass,
                            ScenarioSpec, TimeSpec, dump_spec)

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tier1")


# ---------------------------------------------------------------- helpers ----

def N(id, gov="estate", I=False, X=True, A=True, zones=(), state="state", vis=True):
    return Node(id=id, governance=gov, interface=I, execution_pathway=X,
                authority=A, zones=list(zones), state_object=state, visible=vis)


def conn(a, b):
    return Relation(a, b, Condition.INTERFACE, RelationClass.CONNECTION)


def chan(root, m, g):
    return Relation(root, m, Condition.EXECUTION_PATHWAY, RelationClass.CHANNEL,
                    conferral=True, group=g)


def cp(ctl, m, g):
    return Relation(ctl, m, Condition.AUTHORITY, RelationClass.CONTROL_PLANE,
                    conferral=True, group=g)


def dep(up, down):
    return Relation(up, down, Condition.EXECUTION_PATHWAY, RelationClass.DEPENDENCY)


GOV = [Governance("estate", True), Governance("vendor", False)]


def spec(id, desc, nodes, rels, entry, max_steps=20):
    return ScenarioSpec(id=id, description=desc, governance=GOV, nodes=nodes,
                        relations=rels, entry_node=entry, deterministic=True,
                        time=TimeSpec(max_steps=max_steps))


SET = []   # (spec, expectations)


def add(s, must_reach=(), must_not_reach=(), reach_step=None, cut_removals=None,
        claim=""):
    SET.append((s, {"claim": claim,
                    "must_reach": sorted(must_reach),
                    "must_not_reach": sorted(must_not_reach),
                    "reach_step": reach_step or {},
                    "cut_removals": cut_removals or {}}))


# ---------------------------------------------------------- scenarios ----

# c01 connection chain: lateral movement through zone adjacency, one hop per step
add(spec("c01_connection_chain", "Three zones in a chain; each hop takes one step.",
         [N("a", I=True, zones=[0, 1]), N("b", zones=[1, 2]), N("c", zones=[2, 3]), N("d", zones=[3])],
         [conn("a", "b"), conn("b", "c"), conn("c", "d")], "a"),
    must_reach=["a", "b", "c", "d"], reach_step={"b": 1, "c": 2, "d": 3},
    claim="1B system-level Interface supplied by connection; Paper 2 one step per hop")

# c02 zone isolation: no relation crosses zones, so the second zone is unreachable
add(spec("c02_zone_isolation", "Two zones with no shared node or relation.",
         [N("a", I=True, zones=[0, 1]), N("b", zones=[1]), N("c", zones=[2]), N("d", zones=[2])],
         [conn("a", "b"), conn("c", "d")], "a"),
    must_reach=["a", "b"], must_not_reach=["c", "d"],
    claim="negative control: absent Interface relation blocks reach")

# c03 no admission at all
add(spec("c03_no_interface", "Node with no external Interface and no zone peers.",
         [N("a", I=True, zones=[0, 1]), N("b", zones=[1]), N("island", zones=[])],
         [conn("a", "b")], "a"),
    must_reach=["a", "b"], must_not_reach=["island"],
    claim="negative control: 1A Interface necessary")

# c04 no execution pathway
add(spec("c04_no_execution_pathway", "Adjacent node lacks Execution Pathway and has no X supplier.",
         [N("a", I=True, zones=[0, 1]), N("b", X=False, zones=[1]), N("c", zones=[1])],
         [conn("a", "b"), conn("a", "c")], "a"),
    must_reach=["a", "c"], must_not_reach=["b"],
    claim="negative control: 1A Execution Pathway necessary")

# c05 no authority
add(spec("c05_no_authority", "Adjacent node lacks Authority and has no A supplier.",
         [N("a", I=True, zones=[0, 1]), N("b", A=False, zones=[1]), N("c", zones=[1])],
         [conn("a", "b"), conn("a", "c")], "a"),
    must_reach=["a", "c"], must_not_reach=["b"],
    claim="negative control: 1A Authority necessary")

# c06 channel delivery from an external root (supply chain), members only
add(spec("c06_channel_delivery", "Vendor root delivers to channel members only; non-member untouched.",
         [N("vendor", "vendor", I=True, state="feed"), N("m1", zones=[1]), N("m2", zones=[2]), N("other", zones=[3])],
         [chan("vendor", "m1", "ch"), chan("vendor", "m2", "ch")], "vendor"),
    must_reach=["m1", "m2"], must_not_reach=["other"], reach_step={"m1": 1, "m2": 1},
    claim="1B system-of-systems relation; channel bypasses node Interface")

# c07 channel confers X to a member lacking it
add(spec("c07_channel_confers_x", "Member lacks Execution Pathway; channel delivery confers it.",
         [N("vendor", "vendor", I=True, state="feed"), N("m1", X=False, zones=[1]), N("peer", zones=[1])],
         [chan("vendor", "m1", "ch"), conn("m1", "peer")], "vendor"),
    must_reach=["m1", "peer"], reach_step={"m1": 1, "peer": 2},
    claim="1B conferral: a relation supplies a condition the node lacks")

# c08 control plane conferral: members lacking A are reached through the plane; one has no admission and is not
add(spec("c08_control_plane_conferral", "Controller compromised laterally; plane confers A to members.",
         [N("a", I=True, zones=[0, 1]), N("ctl", zones=[1]), N("m1", A=False, zones=[2]),
          N("m2", A=False, zones=[2]), N("m_planeonly", A=False, zones=[])],
         [conn("a", "ctl"), conn("m1", "m2"), cp("ctl", "m1", "cp"), cp("ctl", "m2", "cp"), cp("ctl", "m_planeonly", "cp")], "a"),
    must_reach=["ctl", "m1", "m2", "m_planeonly"],
    reach_step={"ctl": 1, "m1": 3, "m2": 3, "m_planeonly": 3},
    claim="1B Authority conferred through control plane; plane membership is itself admission")

# c09 detection window timing: reach steps are exact through a chain with a plane in it
add(spec("c09_cp_timing", "Plane ownership one step after controller activation, push one step later.",
         [N("a", I=True, zones=[0, 1]), N("ctl", zones=[1]), N("m", A=False, zones=[5])],
         [conn("a", "ctl"), cp("ctl", "m", "cp")], "a"),
    must_reach=["ctl", "m"], reach_step={"ctl": 1, "m": 3},
    claim="Paper 2 Time: one-step detection window at each stage")

# c10 dependency cascade bypasses admission
add(spec("c10_dependency_cascade", "Downstream nodes with no admission fail through dependency.",
         [N("a", I=True, zones=[0, 1]), N("up", zones=[1]), N("d1", zones=[]), N("d2", zones=[])],
         [conn("a", "up"), dep("up", "d1"), dep("d1", "d2")], "a"),
    must_reach=["up", "d1", "d2"], must_not_reach=[], reach_step={"up": 1, "d1": 2, "d2": 3},
    claim="1B dependency relation supplies X; failure propagates without admission")

# c11 dependency cut
add(spec("c11_dependency_cut", "Receiver's only X supply is one dependency.",
         [N("a", I=True, zones=[0, 1]), N("up", zones=[1]), N("r", X=False, zones=[1])],
         [conn("a", "up"), conn("a", "r"), dep("up", "r")], "a"),
    must_reach=["up", "r"], cut_removals={"up": ["r"]},
    claim="1B Cut on dependency: removing the sole X supplier makes r unreachable")

# c12 connection cut
add(spec("c12_connection_cut", "Receiver's only admission is one peer.",
         [N("a", I=True, zones=[0, 1]), N("mid", zones=[1, 2]), N("r", zones=[2])],
         [conn("a", "mid"), conn("mid", "r")], "a"),
    must_reach=["mid", "r"], cut_removals={"mid": ["r"]},
    claim="1B Cut on connection: sole admitting neighbour")

# c13 control-plane cut
add(spec("c13_cp_cut", "Member's only Authority supply is the plane controller.",
         [N("a", I=True, zones=[0, 1]), N("ctl", zones=[1]), N("m", A=False, zones=[1])],
         [conn("a", "ctl"), conn("a", "m"), cp("ctl", "m", "cp")], "a"),
    must_reach=["ctl", "m"], cut_removals={"ctl": ["m"]},
    claim="1B Cut on control plane: removing the controller removes A")

# c14 channel cut
add(spec("c14_channel_cut", "Member's only X supply is the channel root.",
         [N("vendor", "vendor", I=True, state="feed"), N("m", X=False, zones=[1]), N("peer", I=True, zones=[0, 1])],
         [chan("vendor", "m", "ch"), conn("peer", "m")], "peer"),
    must_reach=["peer", "m"], reach_step={"m": 1}, cut_removals={"vendor": ["m"]},
    claim="1B Cut on channel: a healthy root supplies X standing; removing it makes m unreachable")

# c15 fan-out
add(spec("c15_fanout", "Hub adjacent to six leaves; all reached at step 1.",
         [N("hub", I=True, zones=[0, 1])] + [N(f"l{i}", zones=[1]) for i in range(6)],
         [conn("hub", f"l{i}") for i in range(6)], "hub"),
    must_reach=[f"l{i}" for i in range(6)], reach_step={f"l{i}": 1 for i in range(6)},
    claim="1B Fan-out: one supplier, six receivers, single step")

# c16 governance boundary not crossed inward
add(spec("c16_boundary_not_crossed", "Vendor node has no inbound relation from the estate.",
         [N("a", I=True, zones=[0, 1]), N("b", zones=[1]), N("vendor", "vendor", I=True, state="feed"), N("m", zones=[2])],
         [conn("a", "b"), chan("vendor", "m", "ch")], "a"),
    must_reach=["b"], must_not_reach=["vendor", "m"],
    claim="negative control: system-of-systems relation runs vendor to estate only")

# c17 two planes with an overlapping member
add(spec("c17_two_planes", "Two controllers, one shared member; second plane reached via the shared member.",
         [N("a", I=True, zones=[0, 1]), N("c1", zones=[1]), N("s", A=False, zones=[2]), N("c2", zones=[2]),
          N("m2", A=False, zones=[3])],
         [conn("a", "c1"), cp("c1", "s", "p1"), conn("s", "c2"), cp("c2", "m2", "p2")], "a"),
    must_reach=["c1", "s", "c2", "m2"], reach_step={"c1": 1, "s": 3, "c2": 4, "m2": 6},
    claim="conferral chains across planes with the detection window at each stage")

# c18 mixed (the original micro-system)
from cemt_core.spec import load_spec
_micro = load_spec(os.path.join(os.path.dirname(OUT), "micro_01_supply_chain.yaml"))
_micro = ScenarioSpec(**{**_micro.__dict__, "id": "c18_micro_01_mixed"})
add(_micro, must_reach=["app-1", "app-2", "config-server", "db-1", "web-1", "web-2", "host-3"],
    must_not_reach=["vendor-update"], reach_step={"host-3": 3},
    cut_removals={"db-1": ["app-2"], "config-server": ["host-3"]},
    claim="all relation classes together")

# c19 cycle terminates
add(spec("c19_cycle", "Dependency cycle and connection loop; run must terminate.",
         [N("a", I=True, zones=[0, 1]), N("b", zones=[1]), N("c", zones=[1])],
         [conn("a", "b"), conn("b", "c"), dep("a", "b"), dep("b", "c"), dep("c", "a")], "a"),
    must_reach=["b", "c"], claim="termination under cyclic structure")

# c20 X supplied statically by dependency, reached laterally (supply without failure)
add(spec("c20_static_x_supply", "Node lacks X; dependency supplies it statically; reached by connection while upstream is healthy.",
         [N("a", I=True, zones=[0, 1]), N("r", X=False, zones=[1]), N("up", zones=[9])],
         [conn("a", "r"), dep("up", "r")], "a"),
    must_reach=["r"], must_not_reach=["up"], reach_step={"r": 1}, cut_removals={"up": ["r"]},
    claim="1B: a relation supplies a condition without the supplier being compromised; Cut still holds")


# ---------------------------------------------------------------- write ----

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    manifest = {}
    for s, exp in SET:
        problems = s.validate()
        if problems:
            raise SystemExit(f"{s.id}: {problems}")
        path = os.path.join(OUT, f"{s.id}.yaml")
        dump_spec(s, path)
        manifest[s.id] = {"file": os.path.basename(path), **exp}
    with open(os.path.join(OUT, "manifest.yaml"), "w") as f:
        yaml.safe_dump(manifest, f, sort_keys=False)
    print(f"{len(SET)} scenarios written to {OUT}")
