# cemt_core, Paper 3A skeleton (v0.2)

Frozen reference implementation of the CEMT/STA model, rebuilt from Paper 1A
(Interface, Execution Pathway, Authority), Paper 1B (relation levels, Fan-out,
Cut) and Paper 2 (Structure, Time, Adaptation). This skeleton delivers the
scenario specification and the relation layer with its derived properties.
v0.2 adds the network builder, the spec generator for large runs, Layers 1
to 5 with the IAE entry gate, the step loop with STA ablation, and the locked
collapse rule. The Docker renderer is the next item.

## Decisions built in

| # | Decision | Where it lands |
|---|----------|----------------|
| 1 | Authority replaces Privilege in Layer 1 | `spec.Node.authority`, `RateSpec.authority_rate`; no `privilege_*` field exists |
| 2 | Paper 5 overlay outside the freeze | no strategic fields in the spec; `AdaptationSpec.actions_allowed` is the only hook and defaults to `[remediate]` |
| 3 | Cut and Fan-out derived, never parameters | `relations.RelationTable.cut_table()`, `.fan_out_table()` |
| 4 | Correspondence: structural exact, temporal ordinal, rates out of scope | `ScenarioSpec.deterministic` switches rates off; spec carries defender actions, phantom rates and per-node visibility so later scenarios stay renderable |

## Layout

```
cemt_core/
  spec.py         scenario specification, YAML load/dump, validation
  relations.py    relation table; Supply, Fan-out, Cut, structural capability
  network.py      NetworkState from a spec; generate_spec() from Code80-style
                  structural parameters so large runs are specs too
  layers.py       Layers 1 to 5 as pure functions; IAE Layer 1 gate
  step.py         run_one_trial, run_scenario, STA ablation, collapse rule
  rho_k.py        (next) NGM spectral radius, moved from Code80
  benchmarks.py   (next) B1 to B6 and stage mini-tests, re-pointed
scenarios/
  micro_01_supply_chain.yaml   eight-node correspondence scenario
docker_render/    (separate package, next) spec -> compose + probes
```

Per-paper analysis (formula screen, DeLong, Stage 2 thresholds, evidence
packs) stays out of this package by design.

## Mapping from Code80

| Code80 | cemt_core | Change |
|--------|-----------|--------|
| `node_external`, `privilege_prob`, `execution_prob` | `Node.interface`, `Node.authority`, `Node.execution_pathway` | Privilege becomes Authority; Beta draws move to the network builder and are bypassed in deterministic mode |
| `threat_capability` in the kill chain | `RateSpec.threat_capability` | now explicitly payload/delivery pressure, outside the triad |
| `node_channels_base`, `channel_root`, `channel_is_external` | relations of class `channel`, level `sos` when the root is in an external governance domain | phantom root becomes a real node in a non-defender-controlled governance domain |
| `control_planes`, `cp_member_indices` | relations of class `control_plane` supplying A, `conferral: true` | takeover confers Authority to members |
| `dep_targets` | relations of class `dependency` supplying X | unchanged semantics |
| `dep_out_degree`, channel/CP member counts | `RelationTable.fan_out()` | unified, per class and per level |
| (absent) | `RelationTable.cut()` | new; verified in Docker by container removal |
| `active_layers` | `AblationSpec` (structure / time / adaptation) | STA labels replace layer index lists |
| `SystemBoundary` | `RateSpec.phantom_*_rate` plus `Governance.defender_controlled` | closed is all phantom rates zero |
| P5 `strategic_adaptation` | not carried | outside the freeze |

## Correspondence protocol (for 3A)

Tier 1, structural, exact. Each scenario is run with `deterministic: true` in
both worlds. Agreement is on: the set of nodes reached, the conferral order,
and every Cut triple confirmed by container removal. Pre-registered set of 15
to 20 scenarios including negative controls (a condition absent by design;
`host-3` in `micro_01` has no Interface supply and is such a control).

Tier 2, temporal, ordinal. With `latency_steps` and a remediation agent, event
order and observation lag must agree ordinally. No magnitudes.

Tier 3, rates. Not claimed.

## Modelling facts to carry into 3A

* Connection relations are symmetric: zone co-membership admits in both
  directions, as in Code80. Channel, control-plane and dependency relations
  are directed.
* In deterministic mode Layer 5 remediation does not fire and phantoms are
  never forced; the run traces structural reach only. Tier 2 runs stochastic.
* The `via` label on a reached node lists every relation class that offered
  access in that step, in evaluation order (connection, channel, control
  plane); dependency hits are recorded by Layer 3 only when Layer 2 did not
  already reach the node in the same step.
* Cut density is reported per relation class (`cut_density_by_class()`).
* Performance: Layer 2 loops are Python-level, roughly 0.2 s per trial at
  N=300. Vectorisation is needed before the 1000 x 500 validation budget.

## Run the skeleton

```
python3 -c "
from cemt_core import load_spec, RelationTable
spec = load_spec('scenarios/micro_01_supply_chain.yaml')
rt = RelationTable(spec); print(rt.summary()); print(rt.cut_table())
r = run_scenario(spec)[0]; print(r['reached']); print(r['planes_owned'])"
```

Generated stochastic run with STA ablation:

```
python3 -c "
import dataclasses
from cemt_core import *
g = generate_spec(dict(node_count=300), seed=7)
print('STA', summarise(run_scenario(g, n_trials=20)))
g2 = dataclasses.replace(g, ablation=AblationSpec(adaptation=False))
print('ST ', summarise(run_scenario(g2, n_trials=20)))"
```

## Freeze checklist (for when the model is complete)

1. `CORE_VERSION` set, git tag, SHA-256 of the package recorded.
2. B1 to B6 pass record and stage mini-test record committed alongside.
3. Correspondence set results committed (per-scenario agreement table).
4. Any later structural change requires a declared model revision with a
   new `CORE_VERSION`; parameter and condition changes do not.
