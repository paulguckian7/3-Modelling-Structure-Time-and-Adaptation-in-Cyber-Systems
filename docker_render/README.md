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

1. Install Docker Desktop, WSL2 backend, and start it.
2. Render the bundle (from the repo root):

   ```
   python -m docker_render.render scenarios/micro_01_supply_chain.yaml --out C:\cemt_runs\micro_01
   ```

   Keep run folders outside OneDrive.
3. Run the full trace:

   ```
   cd C:\cemt_runs\micro_01
   docker compose up --build --abort-on-container-exit probe
   ```

   The probe prints the observed and predicted traces and the verdict, and
   writes `out\probe.json`. Exit code 0 means exact match.
4. Cut check for a supplier, for example db-1:

   ```
   docker compose up -d --build
   docker compose stop db-1
   docker compose run --rm probe python probe.py /app/spec.yaml --removed db-1 --out /app/out/probe_no_db-1.json
   docker compose down
   ```

The compose run adds what the local harness cannot: zone and group
networks are real, so a delivery to a node outside the sender's zone fails
at the network, not at a configuration check.
