# FREEZE record

- core version: 0.7
- git commit: 103edc734e7b2a41052340935d801a652aeb5155
- frozen at: 2026-09-16T17:08:37+00:00
- scenarios: 20
- set digest (SHA-256 over all frozen files): `8477d51c0bd25c76fd7cc093f95c02024dfa4d19372acc99ba0bf8b5dfa794bd`

Any change to a frozen file after this record is a model or scenario
revision and requires a new record. Verify with
`python -m docker_render.freeze --verify`.

| File | SHA-256 |
|---|---|
| cemt_core/__init__.py | `67d1c9a7b94b6093…` |
| cemt_core/layers.py | `e869d80b7bae620f…` |
| cemt_core/network.py | `703eb1d7b3d0ca4c…` |
| cemt_core/relations.py | `8757d456ad184634…` |
| cemt_core/spec.py | `b8b7721164f3a908…` |
| cemt_core/step.py | `362613d4d60d7e7a…` |
| docker_render/node_service.py | `2eb8c5b0666f9952…` |
| docker_render/probe.py | `edc0383d40e61227…` |
| docker_render/render.py | `b9a8288261227ba9…` |
| scenarios/tier1/c01_connection_chain.yaml | `4e95efeb608d8b51…` |
| scenarios/tier1/c02_zone_isolation.yaml | `25830936150c4ad5…` |
| scenarios/tier1/c03_no_interface.yaml | `5e1d70b344ca64ef…` |
| scenarios/tier1/c04_no_execution_pathway.yaml | `b17e3215a28fa938…` |
| scenarios/tier1/c05_no_authority.yaml | `2487303758400c6e…` |
| scenarios/tier1/c06_directing_external_trust.yaml | `c0a7e49eaedd9476…` |
| scenarios/tier1/c07_directing_needs_local_x.yaml | `1f4114bfe2906a83…` |
| scenarios/tier1/c08_conferring_control_plane.yaml | `79bb67235a0103c4…` |
| scenarios/tier1/c09_cp_timing.yaml | `8bb31298592f023d…` |
| scenarios/tier1/c10_channel_route_cascade.yaml | `977bc4541efc9c63…` |
| scenarios/tier1/c11_channel_cut.yaml | `8e58e4ba7d30b8c6…` |
| scenarios/tier1/c12_connection_cut.yaml | `132e1f1a689c6aed…` |
| scenarios/tier1/c13_conferring_cut.yaml | `dbd7913c6e28dc7e…` |
| scenarios/tier1/c14_directing_cut.yaml | `f17364f06b1a3c29…` |
| scenarios/tier1/c15_fanout.yaml | `1f74d15580110986…` |
| scenarios/tier1/c16_boundary_not_crossed.yaml | `c2e4ce5845830d1d…` |
| scenarios/tier1/c17_two_planes.yaml | `44bfef06a49c0717…` |
| scenarios/tier1/c18_micro_01_mixed.yaml | `4a3b00c274aac398…` |
| scenarios/tier1/c19_cycle.yaml | `cebd01e9614b4199…` |
| scenarios/tier1/c20_static_x_supply.yaml | `5eebd9d8ce77e501…` |
| scenarios/tier1/manifest.yaml | `35d28e4ae5a0082c…` |
