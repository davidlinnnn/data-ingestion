# Q04 AH first controlled window

Status: **PASS for the v3 exact-graph warm sequence and integrated resource
bounds; #51 remains open**. This was one run with no automatic retry under
`kind-internal-a2a-vs6-local` / `pdf-t09a-validation`, using the new identity
`q04-warm-pod-cgroup-20260924-ah` and prefix
`q04/warm-pod-cgroup-20260924-ah/`. The unchanged 60-second outer admission
passed with 48 samples and zero resets. All 11 Pod pre-inference gates passed
before any workflow, inference or object write.

Five Temporal histories end in `WORKFLOW_EXECUTION_COMPLETED`, and each
business result is `complete` with `processing_complete=true`. The durable
consumer verified all selected work and checked storage reads. Wiki06 (28
pages), YOLO07 (15), AIMA08 (12), native (51), and repeated Wiki06 (28) all
match the frozen v3 graph and local document digests. The first and repeated
Wiki06 documents are byte-identical. AIMA's independent source-image
supplement passed. Native and Wiki06 used the source-reviewed 38-split exact
oracle; no general graph normalization was applied. The
[machine verification](INDEPENDENT-VERIFICATION.json) records each digest and
history terminal event.

The fixed sequence made 29 group requests, reached request-20 recycle, and
observed two unique parser PID/start identities with one recycle and both
exits. All 1,349 process/cgroup samples are complete: maximum gap 0.575233
seconds under the unchanged one-second bound, no incomplete sample, no PSI,
OOM or memory violation, and the 4 GiB all-sample gate passed. The outer VM
controller recorded 1,378 samples, 5,076,701,184 minimum available bytes,
2,545,848,320 maximum cgroup bytes, and no stop. These observations qualify
the integrated operating bounds for this exact producer/runtime.

The Pod-local workload exited zero without force or timeout. Its terminal
manifest is `PASS_CANDIDATE`; all 93 inventory entries and their SHA-256
digests passed independent readback, and no extra evidence files were found.
The outer controller exited zero with no primary or deletion error. The raw
`terminal_stop_proven=false` field means it did not initiate a stop after
natural success. Exit code zero, `cleanup-complete.json`, the sealed terminal
manifest and absent owned runtime establish terminal cleanup. Independent
cluster reads found no AH Pod, Deployment or ConfigMap; the evidence PVC is
Bound at UID `eb537810-f072-4e94-8e64-c50c829ed2c1`, and the existing
checker confirmed all 32 held Deployments exact/off. Raw evidence remains at
`/private/tmp/q04-warm-pod-cgroup-20260924-ah` and on the retained PVC.

AH's reviewed contract deliberately labels the *complete* warm acceptance row
pending: it has not yet compared a standalone v3 fresh baseline for Wiki06,
YOLO07 and native against the warm documents. No v3 restored or exact-replay
mode ran, nor the changed-profile rejection, process/Pod interruption and
recovery, telemetry-loss injection or #44 bounds handoff. The next runtime
must use a new identity/prefix and prove the v3 fresh/restored/replay matrix
with the same fail-stop guards. Historical A–AG evidence and object prefixes
remain untouched; no ticket update has been posted.
