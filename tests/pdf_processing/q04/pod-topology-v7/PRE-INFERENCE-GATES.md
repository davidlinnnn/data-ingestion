# Q04 fixture 07 pre-inference gates

Window H executes the following as one fail-closed gate set after Pod readiness
and before any workflow, object write, parser load or inference. The gate set is
implemented by `pod_preflight_h.py`; every row runs once even when another row
fails, and the complete PASS/FAIL record is written locally and once inside the
run-owned evidence directory before the controller stops. The workload refuses
to start without a complete all-PASS record.

| Gate | Exact check | Failure state |
| --- | --- | --- |
| Pod image | Reviewed image reference, repository platform-manifest identity, container ID, zero restarts | workload `NOT_STARTED` |
| PVC/PV backend | New H PVC only; `standard`; `rancher.io/local-path`; `hostPath DirectoryOrCreate`; pinned node; exact claim/PV UIDs | workload `NOT_STARTED` |
| Mount root | `/q04-evidence` is a real directory, not a symlink, initially empty, writable and searchable by UID/GID 1000 | workload `NOT_STARTED` |
| Run directory | Exclusive creation of `/q04-evidence/q04-yolo-pod-cgroup-20260920-h`; `lstat`; no symlink; UID/GID 1000; mode `0700` | workload `NOT_STARTED` |
| Durable filesystem | File fsync, atomic rename, directory fsync, byte-for-byte readback, cleanup fsync and 128 MiB stop watermark | workload `NOT_STARTED` |
| Python/executable | `sys.executable` is the fixed readable and executable `/experiment/.venv/bin/python`; Python `3.12.13` | workload `NOT_STARTED` |
| Packages/imports | Import `boto3`, `temporalio`, `PIL`, `psutil`; exact frozen distribution versions from retained reviewed evidence | workload `NOT_STARTED` |
| Models | Resolve the 14 reviewed Hugging Face cache artifacts and three RapidOCR package artifacts at their runtime locations; require exact SHA-256 and readability for all 17 | workload `NOT_STARTED` |
| Cgroup | `memory.max=5 GiB`; initial `oom`, `oom_kill`, `oom_group_kill` all zero | workload `NOT_STARTED` |
| Capacity configuration | Exact H phase/scope digest, 1,500/180/60/825/300-second budgets, 4.5 GiB outer and 3 GiB per-case gates, 4/5 GiB cgroup thresholds, no retry | workload `NOT_STARTED` |
| Bundle | `inputs.json` SHA-256 `67eba79d6125c536ab728edb4f7d8ee070d8aead49384f4afc3a48c78267d420` | workload `NOT_STARTED` |
| Staged sources | Every producer and harness byte matches the generated H source manifest | workload `NOT_STARTED` |
| Workload imports and reviewed contract | Import the exact workload entrypoint and Pod support modules, then run the real reviewed-input validator against the H runtime manifest, projected artifacts and frozen bundle | workload `NOT_STARTED` |
| Temporal | Pod-side health succeeds and no workflow is running | workload `NOT_STARTED` |
| Object store | Pod-side health is HTTP 200, bucket versioning is enabled and the new H prefix is unused | workload `NOT_STARTED` |

The controller binds Kubernetes status to the reviewed registry/image chain,
then stages that accepted identity into the control volume. The Pod-side gate
set rechecks and emits it with every other row in one result. The object checks
are read-only. Candidate source
upload remains the first operation of `pod_init_h.py` after workload start and
therefore is not represented as a preflight success.

No live H Pod has exercised this list. A read-only probe of the existing
coordinator using the same pinned image confirmed that 14 reviewed artifacts
are in the Hugging Face cache and the three RapidOCR ONNX artifacts are in the
installed package's `models` directory. Unreferenced cache bookkeeping and
additional cached models are not output dependencies and are not counted as an
acceptance gate. Local tests prove the filesystem and validation logic,
including rejection of a pre-existing path, symlink, wrong owner, wrong mode,
model hash drift and source hash drift. Cluster feasibility
of UID/GID 1000 creating the child on this specific hostPath remains an explicit
runtime gate.
