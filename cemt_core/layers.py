"""
Layers 1 to 5 as pure functions returning StateDelta objects.

Structure  (Paper 2 S): Layer 1 entry, Layer 2 systematic, Layer 3 systemic
Time       (Paper 2 T): Layer 4 drift and the infected -> compromised delay
Adaptation (Paper 2 A): Layer 5 remediation and adaptive capacity a(t)

Layer 1, IAE gate (decision D1)
  A node can be entered only if I ∧ X ∧ A holds structurally (from the
  supply table), and the payload's processing then succeeds with probability
  x_prob · a_prob · T. Threat capability T is payload and delivery pressure,
  outside the triad (Paper 1A, Section 3.7).

Deterministic mode (structural correspondence tier)
  Every gating probability is 1.0 and Layer 5 remediation does not fire, so
  the run traces the structural reach of an entry and nothing else. Tier 2
  (temporal, ordinal) runs stochastic with remediation on.

Attacker access through relations
  connection     compromised peer i reaches j; j's own X and A gate the hit
  channel        compromised root i delivers to member j; I is bypassed
                 (pre-positioned delivery), X is conferred, A gates
  control_plane  owned plane's controller reaches members; A is conferred,
                 X gates
  dependency     compromised upstream i fails j directly (systemic cascade)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

import numpy as np

from .network import NetworkState
from .spec import RelationClass


class NodeState(IntEnum):
    HEALTHY = 0
    INFECTED = 1
    COMPROMISED = 2
    EXFILTRATING = 3


@dataclass
class SystemState:
    compromise: np.ndarray                 # int8 NodeState per node
    drift: np.ndarray                      # float per node
    compromised_at: np.ndarray             # int, -1 if never
    owned_cp: Dict[str, bool]              # control-plane group -> owned
    a: float = 1.0                         # adaptive capacity stock
    step: int = 0
    exec_modifier: np.ndarray = None       # drift-adjusted X gate multiplier
    audit: Dict = field(default_factory=dict)


@dataclass
class StateDelta:
    newly_infected: Optional[np.ndarray] = None    # bool mask
    infected_via: Dict[int, str] = field(default_factory=dict)  # node -> class
    drift_delta: Optional[np.ndarray] = None
    a_delta: float = 0.0
    n_remediated: int = 0
    source: str = ""


def init_state(net: NetworkState) -> SystemState:
    N = net.N
    return SystemState(
        compromise=np.zeros(N, dtype=np.int8),
        drift=np.zeros(N, dtype=float),
        compromised_at=np.full(N, -1, dtype=int),
        owned_cp={g: False for g in net.control_planes},
        exec_modifier=np.ones(N, dtype=float),
        audit={"reached": [], "planes_owned": [], "x_true": [], "x_obs": [],
               "step": [], "remediated": [], "drift_mean": []},
    )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _gate(p: float, det: bool, rng: np.random.Generator) -> bool:
    return True if det else bool(rng.random() < min(max(p, 0.0), 1.0))


def structural_capability(net: NetworkState, st: SystemState, j: int) -> bool:
    """I ∧ X ∧ A for node j from the static supply table. Conferral is
    handled by the relation-class rules in Layer 2; the static table already
    records the supply, so capability is a property of structure alone."""
    return net.capability_static(j)


def x_obs(net: NetworkState, st: SystemState) -> float:
    est = ~net.external
    active = (st.compromise == NodeState.COMPROMISED) & net.visible & est
    return float(active.sum() / max(est.sum(), 1))


def x_true(net: NetworkState, st: SystemState) -> float:
    est = ~net.external
    inf = np.isin(st.compromise, [NodeState.INFECTED, NodeState.COMPROMISED,
                                  NodeState.EXFILTRATING]) & est
    return float(inf.sum() / max(est.sum(), 1))


# ---------------------------------------------------------------------------
# Layer 1: idiosyncratic entry (IAE gate)
# ---------------------------------------------------------------------------

def layer1_entry(net: NetworkState, st: SystemState, entry: int,
                 rng: np.random.Generator) -> Optional[StateDelta]:
    det = net.spec.deterministic
    if not net.interface[entry]:
        return None                                  # no admission relation
    if not structural_capability(net, st, entry):
        return None                                  # X or A absent
    T = net.spec.rates.threat_capability
    p = net.x_prob[entry] * st.exec_modifier[entry] * net.a_prob[entry] * T
    if not _gate(p, det, rng):
        return None
    mask = np.zeros(net.N, dtype=bool)
    mask[entry] = True
    return StateDelta(newly_infected=mask, infected_via={entry: "entry"},
                      source="layer1")


# ---------------------------------------------------------------------------
# Layer 2: systematic propagation over connection, channel, control plane
# ---------------------------------------------------------------------------

def layer2_systematic(net: NetworkState, st: SystemState,
                      rng: np.random.Generator) -> StateDelta:
    det = net.spec.deterministic
    r = net.spec.rates
    T = r.threat_capability
    comp = st.compromise == NodeState.COMPROMISED
    healthy = st.compromise == NodeState.HEALTHY
    prob = np.zeros(net.N)
    via: Dict[int, str] = {}

    def _accumulate(j: int, p: float, cls: str):
        nonlocal prob
        p = min(max(p, 0.0), 1.0)
        if p <= 0:
            return
        prob[j] = 1.0 - (1.0 - prob[j]) * (1.0 - p)
        # record every class that offers access, in evaluation order
        via[j] = cls if j not in via else via[j] + "|" + cls

    # connection: compromised peer i -> j, j's X and A gate the hit
    A = net.access[RelationClass.CONNECTION]
    exposure = (A.T @ comp.astype(float))
    for j in np.flatnonzero((exposure > 0) & healthy):
        if not structural_capability(net, st, j):
            continue
        k = int(exposure[j])
        p_per = r.beta_conn * net.x_prob[j] * st.exec_modifier[j] * net.a_prob[j] * T
        p = 1.0 if det else 1.0 - (1.0 - min(p_per, 1.0)) ** k
        _accumulate(j, p, "connection")

    # channel: compromised root delivers to members; X conferred, A gates
    for g, (root, members) in net.channels.items():
        if not comp[root]:
            continue
        for j in members:
            if not healthy[j] or not structural_capability(net, st, j):
                continue
            p = 1.0 if det else r.synchrony * net.a_prob[j] * T
            _accumulate(j, p, "channel")

    # control plane: owned plane reaches members; A conferred, X gates
    for g, (ctl, members) in net.control_planes.items():
        if not st.owned_cp.get(g, False):
            continue
        for j in members:
            if not healthy[j] or not structural_capability(net, st, j):
                continue
            p = 1.0 if det else (r.beta_conn * min(1.0, r.authority_boost)
                                 * net.x_prob[j] * st.exec_modifier[j] * T)
            _accumulate(j, p, "control_plane")

    if det:
        hits = (prob > 0) & healthy
    else:
        hits = (rng.random(net.N) < prob) & healthy
    return StateDelta(newly_infected=hits,
                      infected_via={j: via[j] for j in np.flatnonzero(hits)},
                      source="layer2")


# ---------------------------------------------------------------------------
# Layer 3: systemic (control-plane takeover, dependency cascade)
# ---------------------------------------------------------------------------

def layer3_systemic(net: NetworkState, st: SystemState,
                    rng: np.random.Generator) -> StateDelta:
    det = net.spec.deterministic
    r = net.spec.rates
    comp = st.compromise == NodeState.COMPROMISED
    healthy = st.compromise == NodeState.HEALTHY

    # takeover: controller compromised -> owned (conferral of A downstream);
    # otherwise compromised members may take it over stochastically
    for g, (ctl, members) in net.control_planes.items():
        if st.owned_cp.get(g, False):
            continue
        if comp[ctl]:
            st.owned_cp[g] = True
            st.audit["planes_owned"].append((st.step, g, "controller"))
            continue
        if det:
            continue
        k = int(comp[members].sum())
        if k == 0:
            continue
        p = 1.0 - (1.0 - r.control_plane_takeover_rate) ** k
        if rng.random() < p:
            st.owned_cp[g] = True
            st.audit["planes_owned"].append((st.step, g, "members"))

    # dependency cascade: compromised upstream fails healthy downstream
    D = net.access[RelationClass.DEPENDENCY]
    base_tp = 1.0 - 1.0 / (1.0 + r.dependency_factor)
    hits = np.zeros(net.N, dtype=bool)
    via: Dict[int, str] = {}
    for i in np.flatnonzero(comp):
        for j in np.flatnonzero(D[i]):
            if not healthy[j] or hits[j]:
                continue
            p = 1.0 if det else min(1.0, base_tp * (1.0 + st.drift[j]))
            if _gate(p, det, rng):
                hits[j] = True
                via[j] = "dependency"
    return StateDelta(newly_infected=hits, infected_via=via, source="layer3")


# ---------------------------------------------------------------------------
# Layer 4: temporal drift
# ---------------------------------------------------------------------------

def layer4_temporal(net: NetworkState, st: SystemState) -> StateDelta:
    inc = net.spec.time.drift_increment
    comp = st.compromise == NodeState.COMPROMISED
    lat = st.compromise == NodeState.INFECTED
    dd = np.zeros(net.N)
    xt = x_true(net, st)
    dd[comp] += inc * (1.0 + 5.0 * xt)
    dd[lat] += inc * 0.5
    return StateDelta(drift_delta=dd, source="layer4")


def update_exec_modifier(net: NetworkState, st: SystemState) -> None:
    edb = net.spec.rates.execution_drift_boost
    st.exec_modifier = 1.0 + edb * st.drift


# ---------------------------------------------------------------------------
# Layer 5: adaptation (remediation acting on x_obs, capacity a(t))
# ---------------------------------------------------------------------------

def layer5_adaptation(net: NetworkState, st: SystemState,
                      rng: np.random.Generator) -> StateDelta:
    det = net.spec.deterministic
    ad = net.spec.adaptation
    xo = x_obs(net, st)
    overwhelm = max(0.01, st.a * np.exp(-ad.overwhelm_coefficient * xo))
    n_rem = 0
    if not det:
        comp = st.compromise == NodeState.COMPROMISED
        cand = np.flatnonzero(comp & net.visible & ~net.external)
        for j in cand:
            if rng.random() < ad.synchrony * ad.remediation_capability * overwhelm:
                st.compromise[j] = NodeState.HEALTHY
                st.drift[j] = max(0.0, st.drift[j] - 0.1)
                n_rem += 1
    # adaptive capacity stock
    comp = st.compromise == NodeState.COMPROMISED
    d_end = float(st.drift[comp].mean()) if comp.any() else 0.0
    vis = net.spec.rates  # placeholder to keep signature symmetric
    cc = min(1.0, max(0.0, np.exp(-xo) * np.exp(-0.3 * d_end) * (1 - 0.3 * d_end)))
    degrade = ad.sigma_x * xo + ad.sigma_d * d_end
    restore = ad.sigma_r * n_rem / max(net.N, 1)
    recovery = ad.tau_a * max(0.0, cc - st.a) * overwhelm
    decay = ad.tau_a * max(0.0, st.a - cc) * (1.0 - overwhelm) * 0.3
    a_next = max(cc * 0.05, min(1.0, st.a + recovery - decay - degrade + restore))
    return StateDelta(a_delta=a_next - st.a, n_remediated=n_rem, source="layer5")


# ---------------------------------------------------------------------------
# delta application and housekeeping
# ---------------------------------------------------------------------------

def apply_delta(net: NetworkState, st: SystemState, d: StateDelta) -> None:
    if d.newly_infected is not None:
        idx = np.flatnonzero(d.newly_infected & (st.compromise == NodeState.HEALTHY))
        st.compromise[idx] = NodeState.INFECTED
        for j in idx:
            st.audit["reached"].append((st.step, net.ids[j], d.infected_via.get(int(j), d.source)))
    if d.drift_delta is not None:
        st.drift = np.clip(st.drift + d.drift_delta, 0.0, 1.0)
    if d.a_delta:
        st.a = min(1.0, max(0.0, st.a + d.a_delta))


def activate_infected(st: SystemState) -> None:
    idx = np.flatnonzero(st.compromise == NodeState.INFECTED)
    st.compromise[idx] = NodeState.COMPROMISED
    st.compromised_at[idx] = st.step


def exfiltrate_dwell(net: NetworkState, st: SystemState) -> None:
    dwell = net.spec.time.exfil_dwell_steps
    if dwell <= 0:
        return
    comp = st.compromise == NodeState.COMPROMISED
    idx = np.flatnonzero(comp & (st.compromised_at >= 0)
                         & (st.step - st.compromised_at >= dwell))
    st.compromise[idx] = NodeState.EXFILTRATING


def update_phantoms(net: NetworkState, st: SystemState,
                    rng: np.random.Generator) -> None:
    """External (vendor) nodes compromise exogenously at the phantom rates.
    Closed boundary = all rates zero. Deterministic mode never forces
    phantoms: an external node is compromised only if the spec says so via
    entry_node."""
    if net.spec.deterministic:
        return
    r = net.spec.rates
    for j in np.flatnonzero(net.external):
        if st.compromise[j] != NodeState.HEALTHY:
            continue
        is_root = any(root == j for root, _ in net.channels.values())
        rate = r.phantom_channel_rate if is_root else r.phantom_dep_rate
        if rate > 0 and rng.random() < rate:
            st.compromise[j] = NodeState.COMPROMISED
            st.compromised_at[j] = st.step
            st.audit["reached"].append((st.step, net.ids[j], "phantom"))
