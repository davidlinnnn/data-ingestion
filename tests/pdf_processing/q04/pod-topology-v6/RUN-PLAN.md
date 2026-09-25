# Q04 YOLO Pod cgroup G single-window plan

This is an offline candidate for one future 1,500-second fixture 07
fresh/restored/exact-replay window. It creates a new G identity and a new PVC;
it does not reuse, write or delete the retained A, C, D, E or F PVCs. A later runtime
requires a reviewed commit, exact authorization-scope digest and separate
authorization. Automatic retry is disabled.

## Fixed identity and budgets

- Run: `q04-yolo-pod-cgroup-20260920-g`
- Object prefix: `q04/yolo-pod-cgroup-20260920-g/`
- Deployment: `q04-pod-cgroup-g-activities`, initially zero replicas
- PVC: `q04-pod-cgroup-g-evidence-20260920-g`, 1 GiB, retained
- Application evidence directory:
  `/q04-evidence/q04-yolo-pod-cgroup-20260920-g`
- Authorization scope:
  `b94f7ba6a9abd197d2b30625822bbad5b09a8aba50dad0ef2ae29e1a5938f05d`
- Admission: observe at most 180 seconds until at least 4.5 GiB and PSI zero
  remain continuous for 60 seconds.
- Pre-workload budget: admission, object creation, readiness, mount setup,
  bundle staging and all pre-inference gates must finish while at least 1,125
  seconds remain.
- Workload: 825 seconds maximum with the existing 3 GiB per-case, 4 GiB
  qualification and 5 GiB hard limits.
- Cleanup: the final 300 seconds are reserved and cannot be borrowed.

## Exact order

1. Recheck context, node/boot identity, VM and cgroup OOM baselines, T09a
   health/idle state, new object absence and all 32 held Deployment UIDs at
   replicas/ready zero.
2. Run outer admission without creating a Pod.
3. Create two immutable ConfigMaps, the new G PVC and an inactive Deployment.
4. Scale the exact Deployment UID from zero to one and accept exactly one Pod,
   pinned node, zero restarts and reviewed image identity.
5. Verify the bound `standard` StorageClass and the exact
   `rancher.io/local-path hostPath DirectoryOrCreate` PV/claim relationship.
6. Check the backend-owned mount root is empty, then let UID/GID 1000 exclusively create
   the G run directory at `0700`. Reject any existing path or symlink. Verify
   ownership, durable write/fsync/atomic rename/readback and capacity.
7. Write the exact PVC/PV/directory identity once in the G directory. Copy the
   frozen bundle to the control `emptyDir`; stage capacity and the generated
   source manifest there.
8. Execute every row in `PRE-INFERENCE-GATES.md` once, without fail-fast hiding
   later observations. Persist the complete result locally and inside the G
   directory before evaluating PASS. Any failed row stops before workload.
9. Confirm that 825 workload seconds plus 300 cleanup seconds remain, then start
   the supervisor. Run only fixture 07 fresh, restored and exact replay while
   sampling every 250 ms and incrementally mirroring evidence.
10. Require all oracles, complete graph/source/replay records, resource guards,
    terminal cleanup markers, durable terminal manifest and stable archive
    readback.
11. Stop the local transport, scale and UID-delete the Pod/Deployment, delete
    the two exact ConfigMaps, retain only the G PVC, then recheck OOM/PSI,
    T09a, object health and the 32 held Deployments.

## Stop and evidence semantics

Every failed gate stops the sequence and is never retried automatically. A
failure before supervisor launch is recorded as workload, workflow and
inference `NOT_STARTED`; cleanup does not attempt to read supervisor markers.
Launching the local `kubectl exec` transport is insufficient to change that
classification: only validated publication of `supervisor-ownership.json` and
the bound transport identity proves supervisor start.
The report separates local controller evidence, a retained PVC and workload
evidence. A retained PVC with only infrastructure/preflight records is never
called durable workload evidence.

For a pre-workload failure, cleanup disposition is
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_NOT_STARTED`. After workload start, an
incomplete export is
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_EVIDENCE_INCOMPLETE`. Only a terminal,
read-back, controller-exported workload record is
`CLEANED_WITH_WORKLOAD_EVIDENCE_RETAINED`.

All exits keep the G PVC, remove only UID-fenced G runtime objects, and leave the
32 historical Deployments closed. Uncertain deletion or final health becomes
`NEEDS_INTERVENTION`; the runner never force-deletes an identity it cannot
prove. Historical A/C/D/E/F PVCs, runners and evidence remain unchanged.

The earliest live-only uncertainty is UID/GID 1000 creating the run-owned child
on the new G mount. A read-only inspection of the pinned image confirmed all 17
profile-referenced model artifacts at their runtime locations: 14 in the
Hugging Face cache and three in the installed RapidOCR package. The live gate
still verifies every artifact's exact digest before workload start.
