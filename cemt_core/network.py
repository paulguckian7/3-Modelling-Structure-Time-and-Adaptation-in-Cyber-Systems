"""
Network construction from a ScenarioSpec.

Two entry points:

  build_network(spec, rng)     -> NetworkState
      Realises the structure a spec describes. All structural facts come from
      the relation table; the only stochastic content is the per-node gating
      probability for X and A (Beta draws around the spec rates) and Pareto
      impact weights. In deterministic mode every gating probability is 1.0.

  generate_spec(params, seed)  -> ScenarioSpec
      Produces a spec from structural parameters in the style of Code80
      build_network (zones, channel pool, control-plane pool, dependency
      graph, external vendor roots). Large validation runs use this so that
      every scenario, generated or hand-written, is a ScenarioSpec and is
      therefore renderable to Docker in principle.

Code80 correspondence
  node_external           -> Node.interface
  privilege_prob          -> a_prob (Authority gating), decision D1
  execution_prob          -> x_prob (Execution Pathway gating)
  channel_root external   -> supplier node in a non-defender governance domain
  control_planes matrix   -> control_plane relations with conferral
  dep_targets             -> channel relations (1B Channel / Dependency)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

import numpy as np

from .relations import RelationTable
from .spec import (Condition, Governance, Node, Relation, RelationClass,
                   ScenarioSpec, RateSpec)


# ---------------------------------------------------------------------------
# Realised network
# ---------------------------------------------------------------------------

@dataclass
class NetworkState:
    spec: ScenarioSpec
    table: RelationTable
    ids: List[str]                       # index -> node id
    index: Dict[str, int]                # node id -> index
    N: int
    external: np.ndarray                 # bool, node in non-defender governance
    interface: np.ndarray                # bool, node-level I instance
    x_present: np.ndarray                # bool, node-level X instance
    a_present: np.ndarray                # bool, node-level A instance
    x_prob: np.ndarray                   # float, X gating probability
    a_prob: np.ndarray                   # float, A gating probability
    visible: np.ndarray                  # bool
    impact: np.ndarray                   # float
    # attacker-access adjacency, one boolean matrix per relation class,
    # M[i, j] True when supplier i supplies receiver j through that class
    access: Dict[RelationClass, np.ndarray]
    conferral: np.ndarray                # bool [i, j], supplier compromise confers
    # standing supply of each condition from the relation table (any supplier)
    sup_I: np.ndarray = None
    sup_X: np.ndarray = None
    sup_A: np.ndarray = None
    # directing control planes: group id -> (controller index, member indices)
    control_planes: Dict[str, tuple] = field(default_factory=dict)
    # conferring control planes: group id -> (issuer index, member indices)
    conferring_planes: Dict[str, tuple] = field(default_factory=dict)

    def capability_static(self, j: int) -> bool:
        """I ∧ X ∧ A from the static supply table (any supplier, any state)."""
        return self.table.structural_capability(self.ids[j])


def build_network(spec: ScenarioSpec, rng: np.random.Generator) -> NetworkState:
    table = RelationTable(spec)
    ids = [n.id for n in spec.nodes]
    index = {nid: i for i, nid in enumerate(ids)}
    N = len(ids)

    gov_ctl = {g.id: g.defender_controlled for g in spec.governance}
    external = np.array([not gov_ctl[n.governance] for n in spec.nodes])
    interface = np.array([n.interface for n in spec.nodes])
    x_present = np.array([n.execution_pathway for n in spec.nodes])
    a_present = np.array([n.authority for n in spec.nodes])
    visible = np.array([n.visible for n in spec.nodes])
    impact = np.array([float(n.impact) for n in spec.nodes])

    if spec.deterministic:
        x_prob = np.ones(N)
        a_prob = np.ones(N)
    else:
        x_prob = _beta_with_mean(spec.rates.execution_rate,
                                 spec.rates.control_variance, N, rng)
        a_prob = _beta_with_mean(spec.rates.authority_rate,
                                 spec.rates.control_variance, N, rng)

    access = {rc: np.zeros((N, N), dtype=bool) for rc in RelationClass}
    conferral = np.zeros((N, N), dtype=bool)
    control_planes: Dict[str, tuple] = {}
    conferring_planes: Dict[str, tuple] = {}
    cpd_members: Dict[str, List[int]] = {}
    cpd_ctl: Dict[str, int] = {}
    cpc_members: Dict[str, List[int]] = {}
    cpc_iss: Dict[str, int] = {}

    for r in spec.relations:
        i, j = index[r.supplier], index[r.receiver]
        access[r.relation_class][i, j] = True
        if r.relation_class == RelationClass.CONNECTION:
            access[r.relation_class][j, i] = True     # adjacency is symmetric
        if r.conferral:
            conferral[i, j] = True
        if r.relation_class == RelationClass.CONTROL_PLANE_DIRECTING:
            g = r.group or f"cpd-{r.supplier}"
            cpd_ctl[g] = i
            cpd_members.setdefault(g, []).append(j)
        if r.relation_class == RelationClass.CONTROL_PLANE_CONFERRING:
            g = r.group or f"cpc-{r.supplier}"
            cpc_iss[g] = i
            cpc_members.setdefault(g, []).append(j)

    for g, m in cpd_members.items():
        control_planes[g] = (cpd_ctl[g], np.array(sorted(set(m))))
    for g, m in cpc_members.items():
        conferring_planes[g] = (cpc_iss[g], np.array(sorted(set(m))))

    sup = {c: np.array([len(table.supply(nid, c)) > 0 for nid in ids]) for c in Condition}

    return NetworkState(
        spec=spec, table=table, ids=ids, index=index, N=N,
        sup_I=sup[Condition.INTERFACE], sup_X=sup[Condition.EXECUTION_PATHWAY],
        sup_A=sup[Condition.AUTHORITY],
        external=external, interface=interface,
        x_present=x_present, a_present=a_present,
        x_prob=x_prob, a_prob=a_prob, visible=visible, impact=impact,
        access=access, conferral=conferral,
        control_planes=control_planes, conferring_planes=conferring_planes,
    )


def _beta_with_mean(mean: float, variance_strength: float, size: int,
                    rng: np.random.Generator) -> np.ndarray:
    mean = min(max(mean, 1e-3), 1 - 1e-3)
    v = min(max(variance_strength, 0.0), 1.0)
    conc = max(0.5, 50.0 * (1.0 - v) + 1.0 * v)
    return rng.beta(max(0.1, mean * conc), max(0.1, (1 - mean) * conc), size)


# ---------------------------------------------------------------------------
# Spec generator (large-run path)
# ---------------------------------------------------------------------------

def generate_spec(params: Dict, seed: int = 42, scenario_id: str | None = None,
                  deterministic: bool = False) -> ScenarioSpec:
    """
    Generate a ScenarioSpec from Code80-style structural parameters.

    Recognised keys (defaults follow Code80 BASELINE where one exists):
      node_count, n_zones, avg_internal_zones, interface_rate,
      n_channel_pool, avg_channels_per_node, frac_external_channel_roots,
      n_control_plane_pool, avg_control_planes_per_node, global_cp_span,
      dependency_factor, pareto_alpha, pareto_scale, visibility
    Rate keys are passed through to RateSpec by name where they match.
    """
    rng = np.random.default_rng(seed)
    N = int(params.get("node_count", 500))
    n_zones = max(5, int(params.get("n_zones", 80)))
    avg_int = float(params.get("avg_internal_zones", 1.0))
    i_rate = float(params.get("interface_rate", 0.75))
    n_ch = max(1, int(params.get("n_channel_pool", 25)))
    avg_ch = float(params.get("avg_channels_per_node", 3.0))
    frac_ext = float(params.get("frac_external_channel_roots", 0.3))
    n_cp = max(1, int(params.get("n_control_plane_pool", 5)))
    avg_cp = float(params.get("avg_control_planes_per_node", 2.5))
    cp_span = float(params.get("global_cp_span", 0.3))
    dep = float(params.get("dependency_factor", 2.0))
    vis = float(params.get("visibility", 0.85))
    p_alpha = float(params.get("pareto_alpha", 1.5))
    p_scale = float(params.get("pareto_scale", 100_000.0))

    governance = [Governance("estate", True), Governance("vendor", False)]
    nodes: List[Node] = []
    relations: List[Relation] = []

    # --- estate nodes -------------------------------------------------
    impacts = np.clip(p_scale / (np.maximum(rng.random(N), 1e-9) ** (1 / p_alpha)),
                      1, 1e10)
    zone_members: Dict[int, List[str]] = {z: [] for z in range(n_zones)}
    for k in range(N):
        nid = f"n{k}"
        ext = bool(rng.random() < i_rate)
        n_int = min(max(1, int(rng.poisson(avg_int))), n_zones - 1)
        zs = sorted(int(z) for z in rng.choice(np.arange(1, n_zones), n_int, replace=False))
        if ext:
            zs = [0] + zs
        nodes.append(Node(id=nid, governance="estate", interface=ext,
                          visible=bool(rng.random() < vis),
                          impact=float(impacts[k]), zones=zs))
        for z in zs:
            if z != 0:
                zone_members[z].append(nid)

    # --- connection relations: zone co-membership supplies I -----------
    seen: Set[tuple] = set()
    for z in range(1, n_zones):
        mem = zone_members[z]
        for a in range(len(mem)):
            for b in range(a + 1, len(mem)):
                key = (mem[a], mem[b])
                if key in seen:
                    continue
                seen.add(key)
                relations.append(Relation(mem[a], mem[b], Condition.INTERFACE,
                                          RelationClass.CONNECTION))

    # --- update planes: roots direct members; external roots are vendors,
    #     i.e. directing External Trust (1B 3.5). Members keep local X and A.
    ch_members: Dict[int, List[str]] = {c: [] for c in range(n_ch)}
    for n in nodes:
        k = min(max(0, int(rng.poisson(avg_ch))), n_ch)
        for c in rng.choice(n_ch, k, replace=False) if k else []:
            ch_members[int(c)].append(n.id)
    for c in range(n_ch):
        mem = ch_members[c]
        if not mem:
            continue
        if rng.random() < frac_ext:
            root = f"vendor{c}"
            nodes.append(Node(id=root, governance="vendor", interface=True,
                              visible=False, state_object="update_feed"))
        else:
            root = mem[int(rng.integers(len(mem)))]
        for m in mem:
            if m != root:
                relations.append(Relation(root, m, Condition.AUTHORITY,
                                          RelationClass.CONTROL_PLANE_DIRECTING,
                                          conferral=True, group=f"upd{c}"))

    # --- control planes: controller supplies A to members ---------------
    estate_ids = [n.id for n in nodes if n.governance == "estate"]
    for p in range(n_cp):
        if p == 0:
            k = max(1, int(round(cp_span * len(estate_ids))))
            mem = list(rng.choice(estate_ids, min(k, len(estate_ids)), replace=False))
        else:
            mask = rng.random(len(estate_ids)) < (avg_cp / n_cp)
            mem = [e for e, m in zip(estate_ids, mask) if m]
        if not mem:
            continue
        ctl = mem[int(rng.integers(len(mem)))]
        for m in mem:
            if m != ctl:
                relations.append(Relation(ctl, m, Condition.AUTHORITY,
                                          RelationClass.CONTROL_PLANE_DIRECTING,
                                          conferral=True, group=f"cp{p}"))

    # --- channels (1B): directed routes supplying X --------------------
    if dep > 0 and N >= 2:
        p_edge = dep / max(N - 1, 1)
        E = rng.random((N, N)) < p_edge
        np.fill_diagonal(E, False)
        for i, j in zip(*np.nonzero(E)):
            relations.append(Relation(f"n{i}", f"n{j}", Condition.EXECUTION_PATHWAY,
                                      RelationClass.CHANNEL))

    rate_keys = RateSpec.__dataclass_fields__.keys()
    rates = RateSpec(**{k: params[k] for k in rate_keys if k in params})

    return ScenarioSpec(
        id=scenario_id or f"gen_{seed}",
        description="generated from structural parameters",
        governance=governance, nodes=nodes, relations=relations,
        deterministic=deterministic, rates=rates, seed=seed,
    )
