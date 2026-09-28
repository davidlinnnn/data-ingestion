# Q04 fixture-07 durable-PVC window plan

Status: **historical, executed once, failed readiness, identity consumed**.
This file records the fixed 1,500-second fixture-07
fresh/restored/exact-replay window. It does not authorize
Kubernetes discovery, source upload, object creation, Temporal work, inference,
recovery Pod creation, PVC deletion, or restoration of the 32 held Deployments.

## Fixed payload and admission

The historical entrypoint and authorization digest are the
`historical_exact_single_run_command` and `authorization_scope_sha256` fields
in `RUNNER-MANIFEST.json`. They describe only the consumed execution; the live
`exact_single_run_command` is now `null`. The destination was API
`https://127.0.0.1:58329`, context `kind-internal-a2a-vs6-local`, namespace
`pdf-t09a-validation`, and node `internal-a2a-vs6-local-worker2`. The four
objects are the two hash-named source ConfigMaps, retained PVC
`q04-pod-cgroup-a-evidence-20260919-a`, and inactive Deployment
`q04-pod-cgroup-a-activities` in `WORKER.yaml`. No server-side dry-run is part of
the plan.

Before creation, observe at most 180 seconds and require 60 continuous seconds
with at least 4,831,838,208 available bytes, PSI full avg10 zero, VM OOM kill
zero, healthy and idle T09a services, the fixed coordinator/node/boot identity,
no pre-existing run Pod, and all 32 held Deployment UIDs at replicas/ready zero.
Failure stops without retry or a lowered threshold.

The lease reserves 825 seconds for init plus the three ordered modes and the
last 300 seconds for stop, evidence export and cleanup. Runtime stops on any
identity drift, sample gap, PSI, VM/cgroup OOM increment, restart, cgroup use
above 4 GiB, VM availability below 1.5 GiB, evidence use above 896 MiB, evidence
free below 128 MiB, or evidence-filesystem free below 128 MiB.

## Evidence commit and cleanup

The private bundle and capacity record use `/q04-control`; scratch uses
`/scratch`; durable state/evidence uses `/q04-evidence`. After the claim binds,
the runner records the exact claim UID, PV UID, node affinity, capacity, access
mode, process UID/GID, mount UID/GID/mode, fsGroup write access and no-delete
policy. Records use create-only temporary files, flush, fsync, atomic replace
and directory fsync. The terminal commit contains the complete inventory and is
read back before it can be a PASS candidate. The controller independently
checks that inventory, capacity watermark and volume identity.

Every exit stops owned work, scales the exact Deployment UID to zero, deletes
the exact Pod UID, confirms its CRI runtime and emptyDirs are absent, and deletes
only the recorded Deployment and ConfigMaps by UID. The PVC is omitted from all
delete calls and re-read by UID. Controller export failure does not retain the
worker Pod. API uncertainty yields `NEEDS_INTERVENTION`, never an assertion that
cleanup succeeded. The 32 held Deployments remain off.

## Separately authorized read-only recovery

Recovery is allowed only after main review names the retained claim UID and PV
UID from `outer-cleanup.json`. A new helper Pod must use the same pinned node,
image and UID/GID/fsGroup, disable its service-account token, mount that exact
claim with `readOnly: true`, mount no Secret, start no workflow or inference,
and record the observed claim/PV/node plus mount UID/GID/mode before reading.
It then runs terminal-manifest inventory readback and copies the evidence to a
new local recovery directory. Missing terminal, partial file, digest mismatch,
permission drift or identity mismatch remains `INCOMPLETE`. The helper is
UID-fenced and deleted after export; the PVC remains. Claim deletion is outside
both the execution and recovery plans.

## Executed result

The one authorized execution failed at worker Pod readiness before workflow or
inference. `first-window-evidence/outer-cleanup.json` preserves the runner's
original `NEEDS_INTERVENTION` result. The separate later read-only
`post-run-reconciliation.json` confirms cleanup after the Pod grace period; it
does not rewrite the earlier result. The retained PVC is empty and has no
terminal manifest, so its evidence status is `INCOMPLETE`. The run identity,
prefix, object names, output directory, command and authorization digest in
this plan must not be reused.
