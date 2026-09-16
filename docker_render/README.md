# docker_render, the executable micro-system (light version)

One identical service per container (`node_service.py`, standard library
only). Every container is configured from the ScenarioSpec by environment
variables; the probe drives the system in rounds that correspond one-to-one
with model steps and compares the observed trace with the Python model.

## What is real and what is configured

| Model element | Realisation |
|---------------|-------------|
| Interface (node-level) | `/deliver/entry` accepted only when `INTERFACE=1` |
| Connection relation | zone bridge networks; `/deliver/connection` between peers; supplies I at system level |
| Channel relation | group network plus root token; `/deliver/channel` confers X, bypasses I |
| Control-plane relation | group network plus controller token; controller owns the plane on its first active round, pushes `/deliver/cp` from the next; confers A |
| Dependency relation | `dep` network; `/deliver/dependency` fails downstream directly |
| Execution Pathway | `EXEC_PATHWAY=1`, or a live static supplier (`X_SUPPLIERS`), or conferred by the delivery |
| Authority | `AUTHORITY=1`, or a live static supplier (`A_SUPPLIERS`), or conferred by the delivery |
| Payload | the request body; processing it writes the state object file |
| Detection window | a node infected in round k acts from round k+1 |
| Governance boundary | vendor containers are never given an entry payload by the probe; in deterministic mode they are inert unless named as entry |
| Cut | verified by stopping the supplier container and re-running |

Not represented: rates, drift, remediation. Tier 1 only.

## Without Docker (logic check)

```
python -m docker_render.local_harness scenarios/micro_01_supply_chain.yaml --set
```

Runs the same service as local processes and prints the tier 1 table:
the full trace plus one removal run per Cut supplier. This is also
`test_local_harness_tier1_set` in the test suite.

## With Docker Desktop (Windows)

Install Docker Desktop (WSL2 backend) and start it. Then, from the repo
root, the whole frozen set in one command:

```
python -m docker_render.freeze --verify
python -m docker_render.tier1_set --docker --runs-dir C:\cemt_runs
```

For each scenario this renders a bundle under `C:\cemt_runs\<scenario>`,
builds the `cemt-node` image (once per bundle, cached after the first),
starts fresh containers, runs the probe, and for each declared Cut restarts
fresh containers with the supplier stopped and runs the probe again. It
writes the same table, LaTeX and run record as the local mode, with the
footnote and `mode` field set to `docker`. Keep the runs directory outside
OneDrive. Expect roughly a minute per scenario.

Single scenario by hand, if you want to watch it:

```
python -m docker_render.render scenarios\tier1\c18_micro_01_mixed.yaml --out C:\cemt_runs\c18
cd C:\cemt_runs\c18
docker build -t cemt-node .
docker compose up --abort-on-container-exit probe
docker compose down
```

The compose run adds what the local harness cannot: zone and group
networks are real, so a delivery to a node outside the sender's zone fails
at the network, not at a configuration check.
