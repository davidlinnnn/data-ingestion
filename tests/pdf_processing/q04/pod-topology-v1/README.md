# Q04 fixture-07 worker-Pod runner

Status: **first window failed readiness; run identity consumed**. The original
`NEEDS_INTERVENTION` cleanup result and later read-only reconciliation are
preserved under `first-window-evidence/`. No workflow or inference started.

This package prepares one independent worker-container cgroup for fixture 07
fresh, restored and exact replay. It is **offline and unauthorized** until the
main session grants a separate capacity window whose scope digest matches
`RUNNER-MANIFEST.json`.

- `WORKER.yaml` is an inactive `replicas: 0` Deployment, one retained 1 GiB
  evidence PVC, and two immutable, hash-named private-source ConfigMaps.
- `SOURCE-MANIFEST.json` binds every mounted producer and harness file.
- `RUNNER-MANIFEST.json` binds the consumed run identity, historical command,
  resource limits, time budget and source hashes.
- `RUN-PLAN.md` defines admission, evidence, stop and cleanup behavior.
- `BASE-CURRENT-TESTS.md` records the same-environment broad-suite comparison.
- `EVIDENCE-CAPACITY.json` records prior archive/member/sample maxima, headroom,
  and the full-volume stop watermark.
- `PVC-WINDOW-PLAN.md` fixes the four-object permission scope, 1,500-second
  budget, evidence lifecycle, cleanup outcomes and separately authorized
  read-only recovery contract.

`exact_single_run_command` is `null`, and the runner refuses execution because
the identity has been consumed. `historical_exact_single_run_command` records
what ran; it is not an entrypoint. Any future mutable action requires a new
identity, output path, reviewed manifest and explicit authorization. Importing
the runner and `--offline-check` remain local-only.

Do not retry the rejected server-side dry-run. Local JSON parsing and generated
manifest equality do not prove Kubernetes schema or admission acceptance. A
future authorized window must perform the UID-1000/read-only-source/model
no-inference check after the Pod starts and before initialization or workflow
submission; failure ends the window without inference.

The evidence protocol separates `/q04-evidence` from the input/control
emptyDir and parser scratch. Records are create-only and fsync committed. The
terminal manifest contains the full inventory and is accepted only after
readback. Missing, partial, full, mismatched, or identity-shifted evidence is
incomplete. API cleanup uncertainty is `NEEDS_INTERVENTION`, with no claim that
the Pod stopped. Read-only recovery requires a separate authorization and the
recorded PVC/PV/node/UID/GID/fsGroup identity.

The 4 GiB sampled qualification guard remains the acceptance ceiling. The 5 GiB
container limit supplies cleanup headroom and may still OOM. A separate cgroup
does not guarantee that PDF or model page-cache charges disappear.
