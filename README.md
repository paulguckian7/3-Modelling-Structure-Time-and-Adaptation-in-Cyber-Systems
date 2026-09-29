# cemt_core, Paper 3 Structural Defensive Levers in Systemic Cyber Risk (v0.1)

Frozen reference implementation of the CEMT/STA model, rebuilt from Paper 1A
(Interface, Execution Pathway, Authority), Paper 1B (relation levels, Fan-out,
Cut) and Paper 2 (Structure, Time, Adaptation). This skeleton delivers the
scenario specification and the relation layer with its derived properties.
The step loop, network builder and Docker renderer are the next three items.

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
  network.py      (next) builds the multiplex network from a spec; replaces
                  Code80 build_network, keyed on the relation table
  layers.py       (next) Layers 1 to 5 as pure functions, IAE Layer 1
  step.py         (next) run_one_trial with deterministic mode and ablation
  rho_k.py        (next) NGM spectral radius, moved unchanged from Code80
  collapse.py     (next) locked collapse rule, moved unchanged
  benchmarks.py   (next) B1 to B6 and stage mini-tests, moved and re-pointed
scenarios/
  micro_01_supply_chain.yaml   eight-node correspondence scenario
tests/
  test_core.py    18 tests incl. golden micro_01 trace and tier 1 harness
docker_render/
  node_service.py identical per-container service (stdlib only)
  render.py       spec -> compose.yaml, Dockerfile, bundle
  probe.py        drives rounds, observes, compares with the model
  local_harness.py  same service as local processes; --set runs tier 1
  README.md       Docker Desktop workflow
```

Per-paper analysis (formula screen, DeLong, Stage 2 thresholds, evidence
packs) stays out of this package by design.

## Mapping from Code80

| Code80 | cemt_core | Change |
|--------|-----------|--------|
| `node_external`, `privilege_prob`, `execution_prob` | `Node.interface`, `Node.authority`, `Node.execution_pathway` | Privilege becomes Authority; Beta draws move to the network builder and are bypassed in deterministic mode |
| `threat_capability` in the kill chain | `RateSpec.threat_capability` | now explicitly payload/delivery pressure, outside the triad |
| `node_channels_base`, `channel_root`, `channel_is_external` | `control_plane_directing` rows from an external controller (directing External Trust) | phantom root becomes a real node in a non-defender-controlled governance domain |
| `control_planes`, `cp_member_indices` | `control_plane_directing` rows, `conferral: true` | takeover gives the attacker the controller's position |
| `dep_targets` | `channel` rows supplying X | 1B Channel / Dependency |
| `dep_out_degree`, channel/CP member counts | `RelationTable.fan_out()` | unified, per class and per level |
| (absent) | `RelationTable.cut()` | new; verified in Docker by container removal |
| `active_layers` | `AblationSpec` (structure / time / adaptation) | STA labels replace layer index lists |
| `SystemBoundary` | `RateSpec.phantom_*_rate` plus `Governance.defender_controlled` | closed is all phantom rates zero |
| P5 `strategic_adaptation` | not carried | outside the freeze |

## Correspondence protocol (for 3A)

Tier 1, structural, exact. Each scenario is run with `deterministic: true` in
both worlds. Agreement is on: the set of nodes reached, the conferral order,
and every Cut triple confirmed by container removal. The pre-registered set
is `scenarios/tier1/` (20 scenarios, built by `scenarios/build_tier1_set.py`,
expectations in `manifest.yaml`, run by `python -m docker_render.tier1_set`).
Negative controls are c02 to c05 and c16: a condition or relation absent by
design.

Relation classes are Paper 1B's Table 1 rows, level derived from governance:
* connection (I row): standing admission, symmetric; supplies I.
* channel (X row; Dependency when governance-crossing): standing route;
  supplies X. A compromised node on the route holds a position on
  downstream X.
* control_plane_directing (A row, directing form; External Trust when the
  controller is external): a composition that admits the controller's input
  at the member; supplies I; X and A are local. The vendor update case.
* control_plane_conferring (A row, conferring form): an issuer establishes
  A; supplies A only, admits nothing.
Every relation row is a standing supply; compromise of the supplier
additionally confers a position from which the receiver can be reached.
The tier 1 set found and corrected two earlier misreadings: a vendor update
relation does not supply the member's Execution Pathway (1A CrowdStrike:
the route is local), and the conferring form does not admit.

Tier 2, temporal, ordinal. With `latency_steps` and a remediation agent, event
order and observation lag must agree ordinally. No magnitudes.

Tier 3, rates. Not claimed.

## Run the skeleton

```
python3 -c "
from cemt_core import load_spec, RelationTable
rt = RelationTable(load_spec('scenarios/micro_01_supply_chain.yaml'))
print(rt.summary()); print(rt.cut_table())"
```

## Freeze checklist (for when the model is complete)

1. `CORE_VERSION` set, git tag, SHA-256 of the package recorded.
2. B1 to B6 pass record and stage mini-test record committed alongside.
3. Correspondence set results committed (per-scenario agreement table).
4. Any later structural change requires a declared model revision with a
   new `CORE_VERSION`; parameter and condition changes do not.

## Archetype experiments (Sections V to VIII)

`python -m experiments.archetypes` builds `scenarios/archetypes/*.yaml`, runs
Experiment 1 (Structure, WannaCry-inspired, deterministic), Experiment 2
(Time, CrowdStrike-inspired, deterministic with observation latency and a
rollout schedule) and Experiment 3 (Adaptation, SolarWinds-inspired,
stochastic, paired seeds, open loop vs remediation-only vs remediation plus
trust revocation), under $M_{STA}$, $M_{ST}$, $M_{SA}$, $M_S$ and $M_{TA}$,
and writes `results/archetype_results.md`, `.csv` and `ablation_matrix.tex`
with the H4/H5 verdict.

## Freeze and pre-registration

`python -m docker_render.freeze` records SHA-256 hashes of the core package,
renderer, scenario set and manifest in `FREEZE.md` and `freeze.json`;
`--verify` checks the tree against the record. `tier1_set` writes
`tier1_run_record.json` with the digest it ran against and marks the run
PRE-REGISTERED only if the frozen set verifies. `CHANGES.md` is the
development record, including what the set caught and when.
