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

Honest status of the manifest: it was written alongside the scenarios and
revised at v0.5 as above. It is therefore a development artefact up to the
freeze record; the pre-registered evaluation is the first tier 1 run made
after `python -m docker_render.freeze` with `--verify` passing.
