"""CEMT core: frozen reference implementation for Paper 3A (skeleton, v0.1)."""
from .spec import (ScenarioSpec, Node, Relation, Governance, Condition,
                   RelationClass, Level, AblationSpec, load_spec, dump_spec)
from .relations import RelationTable
CORE_VERSION = "0.1-skeleton"
