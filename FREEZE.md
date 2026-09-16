# FREEZE record

- core version: 0.6-skeleton
- git commit: not in a git checkout
- frozen at: 2026-09-16T16:44:24+00:00
- scenarios: 20
- set digest (SHA-256 over all frozen files): `e4d2982f255367fb16f7199a169a81a2c461b8427febe2167bbde7be42d6348b`

Any change to a frozen file after this record is a model or scenario
revision and requires a new record. Verify with
`python -m docker_render.freeze --verify`.

| File | SHA-256 |
|---|---|
| cemt_core/__init__.py | `fc5179ac46382c20…` |
| cemt_core/layers.py | `691aaff82e4d1b8f…` |
| cemt_core/network.py | `703eb1d7b3d0ca4c…` |
| cemt_core/relations.py | `8757d456ad184634…` |
| cemt_core/spec.py | `f3bad4aec3808551…` |
| cemt_core/step.py | `d27851d9e8ec738c…` |
| docker_render/node_service.py | `2eb8c5b0666f9952…` |
| docker_render/probe.py | `edc0383d40e61227…` |
| docker_render/render.py | `d7697e534bf04704…` |
| scenarios/tier1/c01_connection_chain.yaml | `bd3f5c2a63e939b1…` |
| scenarios/tier1/c02_zone_isolation.yaml | `de6b618b3e0fb190…` |
| scenarios/tier1/c03_no_interface.yaml | `1ebd85571df7ea2c…` |
| scenarios/tier1/c04_no_execution_pathway.yaml | `9b670aeb519a6118…` |
| scenarios/tier1/c05_no_authority.yaml | `0205e7bba5c35c28…` |
| scenarios/tier1/c06_directing_external_trust.yaml | `d055e6ef6ec19b98…` |
| scenarios/tier1/c07_directing_needs_local_x.yaml | `4dc4b95540649171…` |
| scenarios/tier1/c08_conferring_control_plane.yaml | `f0e7373be40440a3…` |
| scenarios/tier1/c09_cp_timing.yaml | `89a286a842ac933e…` |
| scenarios/tier1/c10_channel_route_cascade.yaml | `3e819c15a0857449…` |
| scenarios/tier1/c11_channel_cut.yaml | `a028002e0f32fe5e…` |
| scenarios/tier1/c12_connection_cut.yaml | `9a3925960a4e9f2d…` |
| scenarios/tier1/c13_conferring_cut.yaml | `234ba6bd0ef889f8…` |
| scenarios/tier1/c14_directing_cut.yaml | `2502608a1380f87c…` |
| scenarios/tier1/c15_fanout.yaml | `76d566c2af848622…` |
| scenarios/tier1/c16_boundary_not_crossed.yaml | `8f2daadd736ba3d0…` |
| scenarios/tier1/c17_two_planes.yaml | `487fe61657ceabf8…` |
| scenarios/tier1/c18_micro_01_mixed.yaml | `79002610beefd08a…` |
| scenarios/tier1/c19_cycle.yaml | `5f0abf66fa9e01a2…` |
| scenarios/tier1/c20_static_x_supply.yaml | `737a077e8f1c78a3…` |
| scenarios/tier1/manifest.yaml | `35d28e4ae5a0082c…` |
