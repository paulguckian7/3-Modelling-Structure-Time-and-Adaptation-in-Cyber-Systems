# Development record

Kept so that claims about what the correspondence set caught are checkable
against commits rather than narrated. Tags and commit messages as in the
repository history.

| Version | Commit message | What changed and why |
|---|---|---|
| v0.1 | cemt_core v0.1 skeleton: spec, relation table, micro_01 scenario | Scenario spec, relation table with derived Fan-out and Cut. Relation table drawn **directed**. |
| v0.2 | network builder, layers 1-5 with IAE gate, step loop, STA ablation, Cut tagged by class | Model runs. Authority replaces Privilege in Layer 1. |
| v0.2.1 | test suite, 17 tests including golden micro_01 trace | First golden trace. |
| v0.3 | Docker renderer, node service, probe, local harness; relation table made symmetric for connections | **Failure 1 caught.** The tier 1 Cut removal showed web-2 was not a Cut for app-2 (both implementations admitted app-2 through db-1) while the directed relation table listed it as one. Table made symmetric for Connection. |
| v0.3.1 | bypass system proxy | Windows environment fix, no semantics. |
| v0.3.2 | probe stops on quiescence, unreachable targets cached, system-level I for control-plane delivery | Probe stop rule corrected. |
| v0.4 | tier 1 scenario set (20) with manifest; standing supply and admission-by-membership semantics | First full set. Manifest at this version expected c07's member lacking X to be reached through the vendor "channel", and c08's plane members to be admitted through a "control_plane" that also conferred A. Both implementations agreed with that manifest. |
| v0.5 | relation classes aligned to 1B Table 1; tier 1 set rewritten in 1B terms | **Failures 2 and 3 caught by re-reading Paper 1B against the v0.4 manifest.** (2) A vendor update relation is directing External Trust: it supplies admission and directs Authority; the member's Execution Pathway is local (1A, CrowdStrike). c07 rewritten as a negative control. (3) The conferring Control Plane admits nothing; c08 and c13 rewritten. The v0.4 "channel" class (vendor root conferring X) was removed; "dependency" renamed to 1B Channel. |
| v0.5.1 | LaTeX table emitter | No semantics. |
| v0.6 | freeze tooling, run record, CHANGES.md | This file. Freeze record created; first post-freeze evaluation is the Docker run. |
| v0.6.1 | docker mode for tier1_set; shared image | No semantics. |
| v0.6.2 | image includes numpy; renderer ignores editor caches; freeze ignores editor caches | Environment fixes found on the first Docker attempt; no semantics. Refrozen. A commit and tag at this version are labelled "pre-registered tier 1 evaluation under Docker: 20/20"; **that label is withdrawn**. The runner at v0.6.2 started the probe service on `compose up`, so the explicit probe found nodes already compromised and the run could not have completed; the committed table is the harness result. No Docker evaluation exists before v0.7.1. |
| v0.7.1 | runner starts node services only, force-recreates containers, surfaces probe errors | Fix for the defect above; outside the frozen set, so the v0.7 freeze stands. First genuine Docker evaluation is the run made with this runner. |
| v0.7 | archetype experiments; rollout schedule; observation latency; policy threshold; revoke-trust action; entry_certain | **Declared model revision.** Additive mechanics needed by Experiments 2 and 3: (a) directing planes take a rollout schedule (canary, interval), collapsed to immediate when Time is ablated; (b) the defender observes a compromised visible node only after `latency_steps` (0 when Time is ablated); (c) the fixed policy acts only while $o(t) > \theta_d$; (d) `revoke_trust` withdraws the admission configured for a directing controller with an observed compromised member, i.e. $\Gamma$ acting on IAE status; (e) `entry_certain` makes the disturbance the premise of a stochastic run. Tier 1 is deterministic and unaffected in outcome, but the core changed, so the set is refrozen and the Docker evaluation is re-run at this version. First Experiment 3 run showed remediation-only has no effect under a persistent trusted source (0.70 vs 0.70), which motivated (d) and is retained as the secondary condition. |

Honest status of the manifest: it was written alongside the scenarios and
revised at v0.5 as above. It is therefore a development artefact up to the
freeze record; the pre-registered evaluation is the first tier 1 run made
after `python -m docker_render.freeze` with `--verify` passing.
