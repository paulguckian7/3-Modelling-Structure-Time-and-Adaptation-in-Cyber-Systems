| Scenario | Claim | Exact | Theory (obs) | Theory (model) | Cuts | Pass |
|---|---|---|---|---|---|---|
| c01_connection_chain | 1B system-level Interface supplied by connection; Paper 2 one step per hop | True | ok | ok | - | yes |
| c02_zone_isolation | negative control: absent Interface relation blocks reach | True | ok | ok | - | yes |
| c03_no_interface | negative control: 1A Interface necessary | True | ok | ok | - | yes |
| c04_no_execution_pathway | negative control: 1A Execution Pathway necessary | True | ok | ok | - | yes |
| c05_no_authority | negative control: 1A Authority necessary | True | ok | ok | - | yes |
| c06_channel_delivery | 1B system-of-systems relation; channel bypasses node Interface | True | ok | ok | - | yes |
| c07_channel_confers_x | 1B conferral: a relation supplies a condition the node lacks | True | ok | ok | - | yes |
| c08_control_plane_conferral | 1B Authority conferred through control plane; plane membership is itself admission | True | ok | ok | - | yes |
| c09_cp_timing | Paper 2 Time: one-step detection window at each stage | True | ok | ok | - | yes |
| c10_dependency_cascade | 1B dependency relation supplies X; failure propagates without admission | True | ok | ok | - | yes |
| c11_dependency_cut | 1B Cut on dependency: removing the sole X supplier makes r unreachable | True | ok | ok | -up:ok | yes |
| c12_connection_cut | 1B Cut on connection: sole admitting neighbour | True | ok | ok | -mid:ok | yes |
| c13_cp_cut | 1B Cut on control plane: removing the controller removes A | True | ok | ok | -ctl:ok | yes |
| c14_channel_cut | 1B Cut on channel: a healthy root supplies X standing; removing it makes m unreachable | True | ok | ok | -vendor:ok | yes |
| c15_fanout | 1B Fan-out: one supplier, six receivers, single step | True | ok | ok | - | yes |
| c16_boundary_not_crossed | negative control: system-of-systems relation runs vendor to estate only | True | ok | ok | - | yes |
| c17_two_planes | conferral chains across planes with the detection window at each stage | True | ok | ok | - | yes |
| c18_micro_01_mixed | all relation classes together | True | ok | ok | -db-1:ok -config-server:ok | yes |
| c19_cycle | termination under cyclic structure | True | ok | ok | - | yes |
| c20_static_x_supply | 1B: a relation supplies a condition without the supplier being compromised; Cut still holds | True | ok | ok | -up:ok | yes |

20/20 scenarios pass.
