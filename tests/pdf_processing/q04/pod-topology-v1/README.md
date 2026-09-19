# Q04 fixture-07 worker-Pod runner

Status: **`NOT_RUNTIME_READY`**. The offline runner and review artifacts are
preserved here, but the unresolved durable-evidence failure boundary prevents a
runtime authorization. See `DURABLE-EVIDENCE-FEASIBILITY.md`.

This package prepares one independent worker-container cgroup for fixture 07
fresh, restored and exact replay. It is **offline and unauthorized** until the
main session grants a separate capacity window whose scope digest matches
`RUNNER-MANIFEST.json`.

- `WORKER.yaml` is an inactive `replicas: 0` Deployment plus two immutable,
  hash-named private-source ConfigMaps.
- `SOURCE-MANIFEST.json` binds every mounted producer and harness file.
- `RUNNER-MANIFEST.json` binds the new run identity, exact command, resource
  limits, time budget and executable source hashes.
- `RUN-PLAN.md` defines admission, evidence, stop and cleanup behavior.
- `BASE-CURRENT-TESTS.md` records the same-environment broad-suite comparison.

The command in `exact_single_run_command` is the only intended live entrypoint.
It still requires a separate explicit authorization. Running it uploads private
source in ConfigMaps, atomically creates and scales the owned Deployment, copies the private
fixture bundle, writes a new object-store prefix, starts Temporal workflows, and
deletes the exact owned resources during cleanup. Only server-returned UIDs from
successful creates establish ownership. If evidence export fails, the stopped
UID-bound Pod is retained for explicit recovery rather than destroyed. These are mutable cluster
actions. Importing the runner and `--offline-check` perform none of them.

Do not retry the rejected server-side dry-run. Local JSON parsing and generated
manifest equality do not prove Kubernetes schema or admission acceptance. A
future authorized window must perform the UID-1000/read-only-source/model
no-inference check after the Pod starts and before initialization or workflow
submission; failure ends the window without inference.

The 4 GiB sampled qualification guard remains the acceptance ceiling. The 5 GiB
container limit supplies cleanup headroom and may still OOM. A separate cgroup
does not guarantee that PDF or model page-cache charges disappear.
