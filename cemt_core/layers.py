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

Attacker access through relations (Paper 1B classes; see layer2_systematic)
  connection                compromised peer reaches j; j's X and A gate
  channel                   compromised upstream on j's route reaches j; A gates
  control_plane_directing   owned plane pushes to members; X and A gate
  control_plane_conferring  no push; standing A supply only
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Dict, List, Optional

import numpy as np

from .network import NetworkState
from .spec import DefenderActionKind, RelationClass


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
    owned_at: Dict[str, int] = field(default_factory=dict)  # group -> step owned
    revoked_cp: Dict[str, int] = field(default_factory=dict) # group -> step revoked
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
    """I ∧ X ∧ A for node j from the standing supply table."""
    return bool(net.sup_I[j] and net.sup_X[j] and net.sup_A[j])


def path_capability(net: NetworkState, j: int, supplies: str) -> bool:
    """Capability for a delivery through a relation that itself supplies the
    conditions in `supplies` (e.g. "IX" for a channel): the remaining
    conditions must be supplied standing, by the node or any relation."""
    need_I = "I" not in supplies
    need_X = "X" not in supplies
    need_A = "A" not in supplies
    return bool((not need_I or net.sup_I[j]) and (not need_X or net.sup_X[j])
                and (not need_A or net.sup_A[j]))


def observed_mask(net: NetworkState, st: SystemState) -> np.ndarray:
    """Nodes the defender currently observes as compromised: visible, active,
    and past the observation latency (Time). With Time ablated, latency is 0."""
    lat = net.spec.time.latency_steps if net.spec.ablation.time else 0
    active = np.isin(st.compromise, [NodeState.COMPROMISED, NodeState.EXFILTRATING])
    aged = (st.compromised_at >= 0) & (st.step - st.compromised_at >= lat)
    return active & net.visible & ~net.external & aged


def x_obs(net: NetworkState, st: SystemState) -> float:
    est = ~net.external
    return float(observed_mask(net, st).sum() / max(est.sum(), 1))


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
    if not _gate(p, det or net.spec.entry_certain, rng):
        return None
    mask = np.zeros(net.N, dtype=bool)
    mask[entry] = True
    return StateDelta(newly_infected=mask, infected_via={entry: "entry"},
                      source="layer1")


# ---------------------------------------------------------------------------
# Layer 2: systematic propagation over the 1B relation classes
#
#   connection   compromised peer i -> j. Supplies I; j needs standing X, A.
#   channel      compromised upstream i on j's route -> j. The route is X and
#                admission precedes it (X assessed conditional on admission,
#                1B 3.4); j needs standing A.
#   directing CP owned plane's controller -> members. Composition supplies
#                admission; A is local and directed, X local: j needs
#                standing X and A.
#   conferring CP no push. The issuer supplies A standing (Cut applies);
#                compromise of the issuer confers no position by itself.
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
        via[j] = cls if j not in via else via[j] + "|" + cls

    # connection
    A = net.access[RelationClass.CONNECTION]
    exposure = (A.T @ comp.astype(float))
    for j in np.flatnonzero((exposure > 0) & healthy):
        if not path_capability(net, j, "I"):
            continue
        k = int(exposure[j])
        p_per = r.beta_conn * net.x_prob[j] * st.exec_modifier[j] * net.a_prob[j] * T
        p = 1.0 if det else 1.0 - (1.0 - min(p_per, 1.0)) ** k
        _accumulate(j, p, "connection")

    # channel (route): compromised upstream reaches downstream
    C = net.access[RelationClass.CHANNEL]
    base_tp = 1.0 - 1.0 / (1.0 + r.dependency_factor)
    for i in np.flatnonzero(comp):
        for j in np.flatnonzero(C[i]):
            if not healthy[j] or not path_capability(net, j, "IX"):
                continue
            p = 1.0 if det else min(1.0, base_tp * (1.0 + st.drift[j]) * net.a_prob[j] * T)
            _accumulate(j, p, "channel")

    # directing control plane: owned plane pushes to members, subject to the
    # plane's rollout schedule (Time): canary members first, the rest after
    # the interval; with Time ablated the whole population is pushed at once
    for g, (ctl, members) in net.control_planes.items():
        if not st.owned_cp.get(g, False) or g in st.revoked_cp:
            continue
        sched = net.spec.time.rollout.get(g)
        for j in members:
            if not healthy[j] or not path_capability(net, j, "I"):
                continue
            if sched and net.spec.ablation.time:
                canary = {net.index[c] for c in sched.get("canary", []) if c in net.index}
                since = st.step - st.owned_at.get(g, st.step)
                if j not in canary and since < int(sched.get("interval", 0)) + 1:
                    continue
            p = 1.0 if det else (r.beta_conn * min(1.0, r.authority_boost)
                                 * net.x_prob[j] * st.exec_modifier[j] * net.a_prob[j] * T)
            _accumulate(j, p, "control_plane_directing")

    if det:
        hits = (prob > 0) & healthy
    else:
        hits = (rng.random(net.N) < prob) & healthy
    return StateDelta(newly_infected=hits,
                      infected_via={j: via[j] for j in np.flatnonzero(hits)},
                      source="layer2")


# ---------------------------------------------------------------------------
# Layer 3: systemic (directing control-plane takeover)
# ---------------------------------------------------------------------------

def layer3_systemic(net: NetworkState, st: SystemState,
                    rng: np.random.Generator) -> StateDelta:
    det = net.spec.deterministic
    r = net.spec.rates
    comp = st.compromise == NodeState.COMPROMISED
    for g, (ctl, members) in net.control_planes.items():
        if st.owned_cp.get(g, False):
            continue
        if comp[ctl]:
            st.owned_cp[g] = True
            st.owned_at[g] = st.step
            st.audit["planes_owned"].append((st.step, g, "controller"))
            continue
        if det:
            continue
        k = int(comp[members].sum())
        if k == 0:
            continue
        if rng.random() < 1.0 - (1.0 - r.control_plane_takeover_rate) ** k:
            st.owned_cp[g] = True
            st.owned_at[g] = st.step
            st.audit["planes_owned"].append((st.step, g, "members"))
    return StateDelta(source="layer3")


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
    if not det and xo > ad.threshold:          # fixed policy: u(t)=1 iff o(t) > theta_d
        obs = observed_mask(net, st)
        # revoke trust: withdraw the admission configured for any directing
        # controller one of whose members is observed compromised. This is
        # Gamma acting on the IAE status: the plane ceases to supply I and to
        # direct A, so an external source can no longer re-deliver.
        if DefenderActionKind.REVOKE_TRUST in ad.actions_allowed:
            for g, (ctl, members) in net.control_planes.items():
                if g not in st.revoked_cp and obs[members].any():
                    st.revoked_cp[g] = st.step
                    st.audit.setdefault("revocations", []).append((st.step, g))
        cand = np.flatnonzero(obs)
        for j in cand:
            if rng.random() < ad.synchrony * ad.remediation_capability * overwhelm:
                st.compromise[j] = NodeState.HEALTHY
                st.compromised_at[j] = -1
                st.drift[j] = max(0.0, st.drift[j] - 0.1)
                n_rem += 1
                st.audit.setdefault("remediations", []).append((st.step, net.ids[j]))
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
        is_ctl = any(ctl == j for ctl, _ in net.control_planes.values())
        rate = r.phantom_cp_rate if is_ctl else r.phantom_channel_rate
        if rate > 0 and rng.random() < rate:
            st.compromise[j] = NodeState.COMPROMISED
            st.compromised_at[j] = st.step
            st.audit["reached"].append((st.step, net.ids[j], "phantom"))
