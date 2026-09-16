"""
CEMT scenario specification (Paper 3A).

One machine-readable scenario renders to two worlds:
  - the Python reference model (cemt_core.network / cemt_core.step)
  - the Docker micro-system (docker_render, separate package)

Theory anchors
  Paper 1A  node-level conditions: Interface (I), Execution Pathway (X),
            Authority (A). Payload and delivery sit outside the triad.
  Paper 1B  three relation levels: node, system, system-of-systems (across
            a governance boundary); Fan-out and Cut as structural properties.
  Paper 2   Structure, Time, Adaptation as the three ablatable components.

Decisions recorded (Sept 2026)
  D1  Authority replaces Privilege in Layer 1.
  D2  Paper 5 strategic overlay is outside the frozen model. No fields here.
  D3  Cut and Fan-out are DERIVED from the relation table, never parameters.
  D4  Docker correspondence is claimed at the structural tier (exact) and the
      temporal tier (ordinal); rates are out of scope. The spec carries
      fields later papers need (defender actions, phantom rates, visibility)
      so the correspondence is inherited through the spec.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import yaml


SPEC_VERSION = "0.1"


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class Condition(str, Enum):
    """Paper 1A structural conditions. Payload is deliberately absent."""
    INTERFACE = "I"
    EXECUTION_PATHWAY = "X"
    AUTHORITY = "A"


class RelationClass(str, Enum):
    """
    Paper 1B relation classes (Table 1 rows). Level (system vs system of
    systems) is derived from governance, so Concentration, Dependency and
    External Trust are these same classes with the crossing indicator set.

    connection                 Interface row. Standing admission from a source
                               at another node. Supplies I.
    channel                    Execution Pathway row. Standing route from an
                               interface to a mechanism traversing another
                               node (1B Channel; Dependency when it crosses
                               governance). Supplies X.
    control_plane_directing    Authority row, directing form. A composition
                               I(c,i) ∧ X(i,m) ∧ A(m,q): admission from the
                               controller is configured at the member, X and
                               A are local. Supplies I; directs the exercise
                               of A. External Trust (directing) when the
                               controller is external, e.g. a vendor update
                               agent acting on vendor content.
    control_plane_conferring   Authority row, conferring form. An artefact
                               issued elsewhere establishes A(m,q), e.g. an
                               identity provider. Supplies A only; admits
                               nothing.
    """
    CONNECTION = "connection"
    CHANNEL = "channel"
    CONTROL_PLANE_DIRECTING = "control_plane_directing"
    CONTROL_PLANE_CONFERRING = "control_plane_conferring"


# standing supply per class (Paper 1B Sections 3.4, 3.5)
CLASS_SUPPLIES = {
    RelationClass.CONNECTION:               ("I",),
    RelationClass.CHANNEL:                  ("X",),
    RelationClass.CONTROL_PLANE_DIRECTING:  ("I",),      # A is local and directed
    RelationClass.CONTROL_PLANE_CONFERRING: ("A",),
}
# condition the relation row is declared on (Table 1 row)
CLASS_ROW = {
    RelationClass.CONNECTION:               Condition.INTERFACE,
    RelationClass.CHANNEL:                  Condition.EXECUTION_PATHWAY,
    RelationClass.CONTROL_PLANE_DIRECTING:  Condition.AUTHORITY,
    RelationClass.CONTROL_PLANE_CONFERRING: Condition.AUTHORITY,
}


class Level(str, Enum):
    """Paper 1B analysis level of a condition instance."""
    NODE = "node"                  # wholly within one node
    SYSTEM = "system"              # relation within one governance domain
    SYSTEM_OF_SYSTEMS = "sos"      # relation crosses a governance boundary


class DefenderActionKind(str, Enum):
    """
    Container-level operations the Docker renderer can execute. Included now
    so 4A/4B/5 scenarios remain renderable; 3A exercises only REMEDIATE.
    """
    REMEDIATE = "remediate"        # restore a node to healthy (dynamic part of S)
    REVOKE_TRUST = "revoke_trust"  # withdraw admission configured for a directing
                                   # controller whose members are observed
                                   # compromised (IAE status change: the plane no
                                   # longer supplies I or directs A)
    ISOLATE = "isolate"            # sever a node's relations
    RESET_CONTROL_PLANE = "reset_control_plane"
    RESTORE_VISIBILITY = "restore_visibility"


# ---------------------------------------------------------------------------
# Structural objects
# ---------------------------------------------------------------------------

@dataclass
class Governance:
    """A governance domain. Relations crossing domains are system-of-systems."""
    id: str
    defender_controlled: bool = True   # False = vendor / MSP / external


@dataclass
class Node:
    """
    A node with its intrinsic (node-level) condition instances.

    In the Python model these are the Layer 1 entry gate. In Docker they are
    rendered as: interface -> exposed listener; execution_pathway -> a route
    from that listener to a handler that acts on state; authority -> the
    handler's effective permission over the named state object.
    """
    id: str
    governance: str
    interface: bool = False              # externally admitting listener present
    execution_pathway: bool = True       # listener-to-mechanism route present
    authority: bool = True               # mechanism controls its own state
    state_object: str = "state"          # what Authority is authority over
    visible: bool = True                 # defender can observe this node
    impact: float = 1.0                  # severity weight (Pareto-drawn later)
    zones: List[int] = field(default_factory=list)


@dataclass
class Relation:
    """
    One row of the Paper 1B relation table: node `supplier` supplies
    condition `condition` to node `receiver` through `relation_class`.

    Level is derived (not declared) from governance membership:
      same governance domain     -> SYSTEM
      different governance domain -> SYSTEM_OF_SYSTEMS
    """
    supplier: str
    receiver: str
    condition: Condition
    relation_class: RelationClass
    conferral: bool = False   # supplier compromise confers attacker position
    group: Optional[str] = None   # control-plane identifier


# ---------------------------------------------------------------------------
# Dynamics (Time and Adaptation, Paper 2). Rates live here so the
# structural layer above is rate-free and can be rendered deterministically.
# ---------------------------------------------------------------------------

@dataclass
class TimeSpec:
    latency_steps: int = 2            # steps before a compromised visible node is observed
    drift_increment: float = 0.08
    exfil_dwell_steps: int = 5
    max_steps: int = 50
    # rollout schedule per directing plane: group -> {"canary": [ids], "interval": k}
    # canary members are pushed from the first push step; the rest from
    # interval steps later. With Time ablated the interval is treated as 0.
    rollout: Dict[str, Dict] = field(default_factory=dict)


@dataclass
class AdaptationSpec:
    remediation_capability: float = 0.9
    overwhelm_coefficient: float = 4.0
    synchrony: float = 0.5
    tau_a: float = 0.3
    sigma_x: float = 0.05
    sigma_d: float = 0.03
    sigma_r: float = 0.5
    # fixed policy threshold theta_d: remediation acts only while the observed
    # compromise fraction exceeds it. 0.0 = act on any observation.
    threshold: float = 0.0
    actions_allowed: List[DefenderActionKind] = field(
        default_factory=lambda: [DefenderActionKind.REMEDIATE])


@dataclass
class RateSpec:
    """
    Stochastic rates. Ignored entirely when deterministic=True (structural
    correspondence tier); every gated event then fires with probability 1.
    """
    threat_capability: float = 1.0      # payload/delivery pressure, outside triad
    authority_rate: float = 0.55        # P(A holds) for Beta draw at build
    execution_rate: float = 0.55        # P(X holds) for Beta draw at build
    control_variance: float = 0.1
    beta_conn: float = 0.12
    synchrony: float = 0.5              # fraction of channel members delivered per step
    dependency_factor: float = 2.0      # base_tp = 1 - 1/(1+dependency_factor)
    execution_drift_boost: float = 0.8
    control_plane_takeover_rate: float = 0.08
    authority_boost: float = 2.0
    cp_scaling_factor: float = 0.3
    phantom_channel_rate: float = 0.0   # open boundary forcing, 0 = closed
    phantom_cp_rate: float = 0.0
    phantom_dep_rate: float = 0.0


@dataclass
class AblationSpec:
    """
    Paper 2 pre-registered STA ablation. All three True = STA.
    ST: adaptation=False.  SA: time=False.  TA: structure=False (Layers 2 and
    3 off, Layer 1 entry only).
    """
    structure: bool = True
    time: bool = True
    adaptation: bool = True

    @property
    def label(self) -> str:
        return "".join(c for c, on in (("S", self.structure),
                                       ("T", self.time),
                                       ("A", self.adaptation)) if on) or "none"


# ---------------------------------------------------------------------------
# Top-level scenario
# ---------------------------------------------------------------------------

@dataclass
class ScenarioSpec:
    id: str
    spec_version: str = SPEC_VERSION
    description: str = ""
    governance: List[Governance] = field(default_factory=list)
    nodes: List[Node] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    entry_node: Optional[str] = None     # None = policy-sampled in the model
    entry_certain: bool = False          # Layer 1 passes at the entry node: the
                                         # disturbance is the premise, not sampled
    deterministic: bool = False          # structural correspondence mode
    ablation: AblationSpec = field(default_factory=AblationSpec)
    time: TimeSpec = field(default_factory=TimeSpec)
    adaptation: AdaptationSpec = field(default_factory=AdaptationSpec)
    rates: RateSpec = field(default_factory=RateSpec)
    seed: int = 42

    # ---- lookups --------------------------------------------------------
    def node(self, node_id: str) -> Node:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)

    def governance_of(self, node_id: str) -> Governance:
        gid = self.node(node_id).governance
        for g in self.governance:
            if g.id == gid:
                return g
        raise KeyError(gid)

    def level_of(self, rel: Relation) -> Level:
        if rel.supplier == rel.receiver:
            return Level.NODE
        gs = self.node(rel.supplier).governance
        gr = self.node(rel.receiver).governance
        return Level.SYSTEM if gs == gr else Level.SYSTEM_OF_SYSTEMS

    # ---- validation -----------------------------------------------------
    def validate(self) -> List[str]:
        """Return a list of problems; empty means valid."""
        problems: List[str] = []
        gov_ids = {g.id for g in self.governance}
        node_ids = [n.id for n in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            problems.append("duplicate node ids")
        for n in self.nodes:
            if n.governance not in gov_ids:
                problems.append(f"node {n.id}: unknown governance {n.governance}")
        for r in self.relations:
            for side in (r.supplier, r.receiver):
                if side not in node_ids:
                    problems.append(f"relation {r.supplier}->{r.receiver}: "
                                    f"unknown node {side}")
        if self.entry_node is not None and self.entry_node not in node_ids:
            problems.append(f"entry_node {self.entry_node} not a node")
        if self.entry_node is not None and not self.node(self.entry_node).interface:
            problems.append(f"entry_node {self.entry_node} has no Interface")
        for r in self.relations:
            if r.condition != CLASS_ROW[r.relation_class]:
                problems.append(f"relation {r.supplier}->{r.receiver}: class "
                                f"{r.relation_class.value} sits on row "
                                f"{CLASS_ROW[r.relation_class].value}, not {r.condition.value}")
        if not self.ablation.structure and any(
                r.relation_class != RelationClass.DEPENDENCY for r in self.relations):
            # TA ablation: relations are present in the spec but inert in the
            # model; that is intended, so this is a note rather than an error.
            pass
        return problems


# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------

def _enum(cls, value):
    return cls(value) if not isinstance(value, cls) else value


def load_spec(path: str) -> ScenarioSpec:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return spec_from_dict(raw)


def spec_from_dict(raw: Dict) -> ScenarioSpec:
    spec = ScenarioSpec(
        id=raw["id"],
        spec_version=raw.get("spec_version", SPEC_VERSION),
        description=raw.get("description", ""),
        governance=[Governance(**g) for g in raw.get("governance", [])],
        nodes=[Node(**n) for n in raw.get("nodes", [])],
        relations=[
            Relation(
                supplier=r["supplier"], receiver=r["receiver"],
                condition=_enum(Condition, r["condition"]),
                relation_class=_enum(RelationClass, r["relation_class"]),
                conferral=bool(r.get("conferral", False)),
                group=r.get("group"),
            ) for r in raw.get("relations", [])
        ],
        entry_node=raw.get("entry_node"),
        entry_certain=bool(raw.get("entry_certain", False)),
        deterministic=bool(raw.get("deterministic", False)),
        ablation=AblationSpec(**raw.get("ablation", {})),
        time=TimeSpec(**raw.get("time", {})),
        adaptation=AdaptationSpec(**{
            **raw.get("adaptation", {}),
            "actions_allowed": [
                _enum(DefenderActionKind, a)
                for a in raw.get("adaptation", {}).get("actions_allowed",
                                                        ["remediate"])],
        }),
        rates=RateSpec(**raw.get("rates", {})),
        seed=int(raw.get("seed", 42)),
    )
    problems = spec.validate()
    if problems:
        raise ValueError("invalid scenario spec: " + "; ".join(problems))
    return spec


def dump_spec(spec: ScenarioSpec, path: str) -> None:
    import dataclasses

    def _plain(obj):
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj):
            return {k: _plain(v) for k, v in dataclasses.asdict(obj).items()}
        if isinstance(obj, list):
            return [_plain(x) for x in obj]
        if isinstance(obj, dict):
            return {k: _plain(v) for k, v in obj.items()}
        return obj

    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(_plain(spec), f, sort_keys=False)
