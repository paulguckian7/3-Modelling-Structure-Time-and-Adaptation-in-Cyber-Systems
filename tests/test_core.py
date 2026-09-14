"""
cemt_core test suite. Run with:  python -m pytest tests -q

Golden values below are the deterministic micro_01 trace confirmed on
2026-09-14; changing them requires a declared model revision.
"""
import dataclasses
import numpy as np
import pytest

from cemt_core import (AblationSpec, Condition, RelationClass, RelationTable,
                       classify_collapse, generate_spec, load_spec,
                       run_scenario, spec_from_dict)
from cemt_core.spec import Governance, Node, Relation, ScenarioSpec

import os
MICRO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "scenarios", "micro_01_supply_chain.yaml")


@pytest.fixture
def micro():
    return load_spec(MICRO)


# ---------------------------------------------------------------- spec ----

def test_spec_loads_and_validates(micro):
    assert micro.validate() == []
    assert micro.deterministic is True
    assert micro.ablation.label == "STA"


def test_spec_rejects_unknown_node():
    raw = {"id": "bad", "governance": [{"id": "g"}],
           "nodes": [{"id": "a", "governance": "g", "interface": True}],
           "relations": [{"supplier": "a", "receiver": "zz",
                          "condition": "I", "relation_class": "connection"}]}
    with pytest.raises(ValueError):
        spec_from_dict(raw)


def test_spec_rejects_entry_without_interface():
    raw = {"id": "bad", "governance": [{"id": "g"}],
           "nodes": [{"id": "a", "governance": "g", "interface": False}],
           "entry_node": "a"}
    with pytest.raises(ValueError):
        spec_from_dict(raw)


def test_level_derived_from_governance(micro):
    rt = RelationTable(micro)
    levels = {(r.supplier, r.receiver): r.level.value
              for r in rt.rows if r.supplier != r.receiver}
    assert levels[("vendor-update", "web-1")] == "sos"
    assert levels[("config-server", "app-1")] == "system"


# ------------------------------------------------------------ relations ---

def test_fan_out(micro):
    rt = RelationTable(micro)
    assert rt.fan_out("config-server", relation_class=RelationClass.CONTROL_PLANE) == 3
    assert rt.fan_out("vendor-update") == 2
    assert rt.fan_out_table()["vendor-update"]["sos"] == 2


def test_cut_golden(micro):
    rt = RelationTable(micro)
    cuts = {(s, r, c.value, k.value) for s, r, c, k in rt.cut_table()}
    assert ("db-1", "app-2", "X", "dependency") in cuts
    assert len(cuts) == 4
    assert rt.cut_density_by_class() == {"connection": 3, "channel": 0,
                                         "control_plane": 0, "dependency": 1}


def test_negative_control_lacks_capability(micro):
    rt = RelationTable(micro)
    assert rt.structural_capability("host-3") is False
    assert rt.structural_capability("app-2") is True


def test_cut_is_derived_not_parameter(micro):
    # adding a second X supply to app-2 removes the Cut, nothing else changes
    extra = Relation("app-1", "app-2", Condition.EXECUTION_PATHWAY,
                     RelationClass.DEPENDENCY)
    spec2 = dataclasses.replace(micro, relations=micro.relations + [extra])
    cuts = {(s, r, c) for s, r, c, _ in RelationTable(spec2).cut_table()}
    assert ("db-1", "app-2", Condition.EXECUTION_PATHWAY) not in cuts


# ---------------------------------------------------------- determinism ---

GOLDEN_REACHED = [(0, "web-1"), (1, "config-server"), (1, "app-1"),
                  (2, "db-1"), (3, "app-2"), (4, "web-2")]
GOLDEN_PLANES = [(2, "cp-main", "controller")]


def test_micro_deterministic_trace(micro):
    r = run_scenario(micro)[0]
    assert [(s, n) for s, n, _ in r["reached"]] == GOLDEN_REACHED
    assert r["planes_owned"] == GOLDEN_PLANES
    assert set(r["reached_set"]) == {n for _, n in GOLDEN_REACHED}
    assert "host-3" not in r["reached_set"]
    assert "vendor-update" not in r["reached_set"]


def test_deterministic_is_seed_invariant(micro):
    a = run_scenario(micro, seed=1)[0]["reached"]
    b = run_scenario(micro, seed=999)[0]["reached"]
    assert a == b


def test_cut_verified_by_removal(micro):
    """Structural tier check in Python: removing the Cut supplier db-1 must
    stop app-2 being reached (app-2's only X supply is db-1)."""
    nodes = [n for n in micro.nodes if n.id != "db-1"]
    rels = [r for r in micro.relations if "db-1" not in (r.supplier, r.receiver)]
    spec2 = dataclasses.replace(micro, nodes=nodes, relations=rels)
    r = run_scenario(spec2)[0]
    assert "app-2" not in r["reached_set"]


# ------------------------------------------------------------- ablation ---

def test_structure_ablation_stops_traversal(micro):
    s = dataclasses.replace(micro, ablation=AblationSpec(structure=False))
    r = run_scenario(s)[0]
    assert r["reached_set"] == ["web-1"]
    assert r["ablation"] == "TA"


def test_time_ablation_removes_detection_window(micro):
    s = dataclasses.replace(micro, ablation=AblationSpec(time=False))
    r = run_scenario(s)[0]
    assert r["ablation"] == "SA"
    # infected nodes activate in the same step, so reach completes faster
    full = run_scenario(micro)[0]
    assert max(st for st, _, _ in r["reached"]) <= max(st for st, _, _ in full["reached"])


def test_adaptation_reduces_collapse_stochastic():
    g = generate_spec(dict(node_count=200), seed=11)
    sta = run_scenario(g, n_trials=30)
    st = run_scenario(dataclasses.replace(g, ablation=AblationSpec(adaptation=False)),
                      n_trials=30)
    m = lambda rs: np.mean([r["x_true_max"] for r in rs])
    assert m(st) >= m(sta)          # removing adaptation never helps the defender


def test_no_structure_means_no_collapse_stochastic():
    g = generate_spec(dict(node_count=200), seed=3)
    ta = run_scenario(dataclasses.replace(g, ablation=AblationSpec(structure=False)),
                      n_trials=30)
    assert all(not r["collapsed"] for r in ta)


# ------------------------------------------------------------- collapse ---

def test_collapse_rule():
    assert classify_collapse([0.1, 0.4, 0.4, 0.4]) == 3
    assert classify_collapse([0.4, 0.4, 0.1, 0.4, 0.4]) == -1
    assert classify_collapse([0.3, 0.3, 0.3]) == 2
    assert classify_collapse([]) == -1


# ------------------------------------------------------------ generator ---

def test_generated_spec_is_valid_and_reproducible():
    a = generate_spec(dict(node_count=120), seed=5)
    b = generate_spec(dict(node_count=120), seed=5)
    assert a.validate() == []
    assert len(a.nodes) == len(b.nodes) and len(a.relations) == len(b.relations)
    assert any(n.governance == "vendor" for n in a.nodes)
