| Scenario | Claim | Exact | Theory (obs) | Theory (model) | Cuts | Pass |
|---|---|---|---|---|---|---|
| c01_connection_chain | 1B system-level Interface supplied by connection; Paper 2 one step per hop | True | ok | ok | - | yes |
| c02_zone_isolation | negative control: absent Interface relation blocks reach | True | ok | ok | - | yes |
| c03_no_interface | negative control: 1A Interface necessary | True | ok | ok | - | yes |
| c04_no_execution_pathway | negative control: 1A Execution Pathway necessary | True | ok | ok | - | yes |
| c05_no_authority | negative control: 1A Authority necessary | True | ok | ok | - | yes |
| c06_directing_external_trust | 1B 3.5 directing External Trust: composition admits vendor content; owned at step 1, pushed at step 2 | True | ok | ok | - | yes |
| c07_directing_needs_local_x | negative control: directing form supplies admission and direction, not the route (1A CrowdStrike: X is local) | True | ok | ok | - | yes |
| c08_conferring_control_plane | 1B 3.4 conferring form supplies A only; it admits nothing, so an unadmitted member stays unreached | True | ok | ok | - | yes |
| c09_cp_timing | Paper 2 Time: one-step detection window at each stage | True | ok | ok | - | yes |
| c10_channel_route_cascade | 1B Channel: a compromised node on the route holds a position on downstream X | True | ok | ok | - | yes |
| c11_channel_cut | 1B Cut on channel: removing the sole X supplier makes r unreachable | True | ok | ok | -up:ok | yes |
| c12_connection_cut | 1B Cut on connection: sole admitting neighbour | True | ok | ok | -mid:ok | yes |
| c13_conferring_cut | 1B Cut on the Authority row: removing the issuer removes A | True | ok | ok | -iss:ok | yes |
| c14_directing_cut | 1B Cut on the Interface supplied by a directing plane: removing the controller removes admission | True | ok | ok | -ctl:ok | yes |
| c15_fanout | 1B Fan-out: one supplier, six receivers, single step | True | ok | ok | - | yes |
| c16_boundary_not_crossed | negative control: system-of-systems relation runs vendor to estate only | True | ok | ok | - | yes |
| c17_two_planes | conferral chains across planes with the detection window at each stage | True | ok | ok | - | yes |
| c18_micro_01_mixed | all relation classes together | True | ok | ok | -db-1:FAIL -config-server:ok | NO |
| c19_cycle | termination under cyclic structure | True | ok | ok | - | yes |
| c20_static_x_supply | 1B: a relation supplies a condition without the supplier being compromised; Cut still holds | True | ok | ok | -up:ok | yes |

19/20 scenarios pass.
