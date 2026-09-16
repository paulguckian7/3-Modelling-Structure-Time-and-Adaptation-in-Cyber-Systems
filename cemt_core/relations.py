"""
Relation table and derived structural properties (Paper 1B).

Fan-out(i, class)   number of distinct receivers node i supplies through a
                    given relation class. Counted separately at system and
                    system-of-systems level.

Cut(i, j, c)        True when node i lies on every supply of condition c to
                    node j. Operationalised over conditions per node, which is
                    coarser than 1B's per-operation definition; 3A states this
                    as a simplification and 1B remains authoritative.

Supply(j, c)        The set of suppliers of condition c to node j, including
                    j itself when the node-level instance is present.

Both properties are DERIVED from the relation table (decision D3). Neither is
a parameter and neither has a generative mechanism of its own. Scenario
generation moves them only through the structural knobs that shape the
relation table (pool sizes, concentration, external root fraction, CP span).

Deterministic verification in Docker: remove container i, attempt the
operation on j; failure iff Cut(i, j, c) for some c.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from .spec import CLASS_SUPPLIES, Condition, Level, RelationClass, ScenarioSpec

_COND = {"I": Condition.INTERFACE, "X": Condition.EXECUTION_PATHWAY, "A": Condition.AUTHORITY}


@dataclass
class RelationRow:
    supplier: str
    receiver: str
    condition: Condition
    relation_class: RelationClass
    level: Level
    conferral: bool
    group: str | None


class RelationTable:
    def __init__(self, spec: ScenarioSpec):
        self.spec = spec
        # One row per condition the relation supplies standing (1B 3.4/3.5):
        # connection I; channel X; directing control plane I (A is local and
        # directed, not supplied); conferring control plane A.
        self.rows: List[RelationRow] = []
        for r in spec.relations:
            for c in CLASS_SUPPLIES[r.relation_class]:
                self.rows.append(RelationRow(r.supplier, r.receiver, _COND[c],
                                             r.relation_class, spec.level_of(r),
                                             r.conferral, r.group))
                # connection is symmetric: zone co-membership admits both ways
                if r.relation_class == RelationClass.CONNECTION:
                    self.rows.append(RelationRow(r.receiver, r.supplier, _COND[c],
                                                 r.relation_class, spec.level_of(r),
                                                 r.conferral, r.group))
        # node-level instances: a node supplies its own condition to itself
        for n in spec.nodes:
            for cond, present in ((Condition.INTERFACE, n.interface),
                                  (Condition.EXECUTION_PATHWAY, n.execution_pathway),
                                  (Condition.AUTHORITY, n.authority)):
                if present:
                    self.rows.append(RelationRow(
                        n.id, n.id, cond, RelationClass.CONNECTION,
                        Level.NODE, False, None))

    # ---- supply sets ----------------------------------------------------
    def supply(self, receiver: str, cond: Condition) -> Set[str]:
        return {r.supplier for r in self.rows
                if r.receiver == receiver and r.condition == cond}

    def suppliers_by_condition(self, receiver: str) -> Dict[Condition, Set[str]]:
        return {c: self.supply(receiver, c) for c in Condition}

    # ---- Fan-out --------------------------------------------------------
    def fan_out(self, supplier: str, relation_class: RelationClass | None = None,
                level: Level | None = None) -> int:
        receivers = {
            r.receiver for r in self.rows
            if r.supplier == supplier and r.receiver != supplier
            and (relation_class is None or r.relation_class == relation_class)
            and (level is None or r.level == level)
        }
        return len(receivers)

    def fan_out_table(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = defaultdict(dict)
        for n in self.spec.nodes:
            for rc in RelationClass:
                out[n.id][rc.value] = self.fan_out(n.id, relation_class=rc)
            out[n.id]["sos"] = self.fan_out(n.id, level=Level.SYSTEM_OF_SYSTEMS)
            out[n.id]["total"] = self.fan_out(n.id)
        return dict(out)

    # ---- Cut ------------------------------------------------------------
    def cut(self, supplier: str, receiver: str, cond: Condition) -> bool:
        """True iff `supplier` is the only supply of `cond` to `receiver`."""
        s = self.supply(receiver, cond)
        return supplier in s and len(s) == 1

    def cut_set(self, receiver: str) -> Dict[Condition, Tuple[str, RelationClass] | None]:
        """For each condition, (unique supplier, relation class) if the supply
        set has exactly one member, else None."""
        out: Dict[Condition, Tuple[str, RelationClass] | None] = {}
        for c in Condition:
            rows = [r for r in self.rows
                    if r.receiver == receiver and r.condition == c]
            suppliers = {r.supplier for r in rows}
            if len(suppliers) == 1:
                r0 = rows[0]
                out[c] = (r0.supplier, r0.relation_class)
            else:
                out[c] = None
        return out

    def cut_table(self) -> List[Tuple[str, str, Condition, RelationClass]]:
        """All (supplier, receiver, condition, relation_class) where Cut holds
        and the supplier is a different node. Node-level self-supply is
        excluded, since removing a node trivially removes its own operation.
        The relation class is carried so Cut density can be reported per
        class (Interface-by-adjacency counts, per the Sept 2026 decision)."""
        out: List[Tuple[str, str, Condition, RelationClass]] = []
        for n in self.spec.nodes:
            for c, hit in self.cut_set(n.id).items():
                if hit is not None and hit[0] != n.id:
                    out.append((hit[0], n.id, c, hit[1]))
        return out

    def cut_count(self, supplier: str) -> int:
        """Number of (receiver, condition) pairs for which `supplier` is a Cut."""
        return sum(1 for s, _, _, _ in self.cut_table() if s == supplier)

    def cut_density_by_class(self) -> Dict[str, int]:
        counts: Dict[str, int] = {rc.value: 0 for rc in RelationClass}
        for _, _, _, rc in self.cut_table():
            counts[rc.value] += 1
        return counts

    # ---- structural capability (Paper 1A, Eq. 6 necessity direction) ----
    def structural_capability(self, node_id: str) -> bool:
        """I ∧ X ∧ A holds for the node given the current supply table."""
        return all(len(self.supply(node_id, c)) > 0 for c in Condition)

    # ---- summary --------------------------------------------------------
    def summary(self) -> Dict:
        levels = defaultdict(int)
        for r in self.rows:
            levels[r.level.value] += 1
        return {
            "n_rows": len(self.rows),
            "rows_by_level": dict(levels),
            "n_cut_triples": len(self.cut_table()),
            "max_fan_out": max((self.fan_out(n.id) for n in self.spec.nodes),
                               default=0),
            "nodes_with_capability": sum(
                1 for n in self.spec.nodes if self.structural_capability(n.id)),
        }
