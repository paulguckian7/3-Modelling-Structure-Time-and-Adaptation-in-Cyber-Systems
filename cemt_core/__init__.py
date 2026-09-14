"""CEMT core: frozen reference implementation for Paper 3A (v0.2 skeleton)."""
from .spec import (ScenarioSpec, Node, Relation, Governance, Condition,
                   RelationClass, Level, AblationSpec, load_spec, dump_spec)
from .relations import RelationTable
from .network import build_network, generate_spec
from .step import run_one_trial, run_scenario, summarise, classify_collapse
CORE_VERSION = "0.2-skeleton"
