# Q04 I single-window result

**FAIL_TRANSIENT_SCRATCH_EVIDENCE_CONTRACT; no retry.** Executed source commit:
`41a8816` (repairs started in `49eba63`); scope digest
`256644f00131ded32ed92073e0503819167c8d0e83b7759bf12f59f950e0a851`.
Identity `q04-yolo-pod-cgroup-20260920-i`; unchanged kind node, image, producer,
oracle, parser budgets and acceptance thresholds. The execution log and original
controller evidence are retained, including the runner's `pod-cgroup-iealth-*`
filenames; they have not been renamed after execution.

## Results and causal order

Outer admission and all 11 pre-inference gates passed. Fresh started at
17:29:08.259131 UTC on 2026-09-19. Temporal event 13 at 17:29:20.305899 records
successful completion of group 1–5; event 17 schedules the next group. Normal
Activity scratch cleanup removed files previously enumerated by the incremental
mirror. Its strict durable-inventory rule treats disappearance as corruption.

At 17:29:21.127449 the controller persisted this primary error and stopped.
At .204170 it signaled the owned supervisor; at .456252 the supervisor recorded
KeyboardInterrupt and interrupted the matrix group. Temporal cancellation at
.458686 led to Activity cancellation and workflow COMPLETED at .469302 with
business failed/activity_budget_exhausted, registered_pages=5 and
processing_complete=false. There is no Activity failed/timed-out history event.
The business error is again the cancellation fallback, not a measured deadline
exhaustion. Restored and exact replay did not start; no fresh acceptance index.

194 controller samples had node full avg10=0, VM OOM=0, minimum MemAvailable
6,678,102,016 bytes, max worker cgroup 1,744,384,000 bytes, max gap .527069s.
Cgroup full avg10 did reach .18: this different scope was captured directly,
without claiming node PSI was positive. The recovered attribution has 339
samples, max cgroup 1,786,847,232 bytes and no OOM events. These partial-window
measurements do not qualify the full fixture or integrated operating bounds.

The stopped sample stream and controller-stop.json make the primary failure
classifiable. The new raw node/cgroup fields and stop timestamps operated live.
The rejecting PSI-sample preservation remains proven by local regression rather
than a new runtime PSI breach. H's missing exact outer sample remains unknown.

## Cleanup and evidence disposition

The repaired directory filter ran against the actual worker-1/worker-1.log
layout. Worker stopped at 17:29:32.348612; workload exited at .546133, rc=-2,
not timed out and not forced. The supervisor wrote cleanup-complete.json and a
durable terminal manifest: cleanup_complete=true, workload_succeeded=false,
status=INCOMPLETE. This is successful sealing of a failed workload, not ingestion
success.

Automatic controller export failed. The existing transport mirror retained
transient files, then also rejected the >5s receipt gap during graceful cleanup;
its fingerprint could not match the final stable PVC inventory. Original
outer-cleanup disposition remains
`CLEANED_WITH_PVC_RETAINED_WORKLOAD_EVIDENCE_INCOMPLETE` and
controller_export_complete=false. Do not retroactively promote this field.

After cleanup, a read-only export through the already-existing node recovered
the retained PVC into `retained-pvc-readonly/`. All 38 terminal inventory entries
match byte count and SHA-256; inventory digest and exact final file set also
match. The original partial controller mirror remains separately in `evidence/`.
The retained raw tar is `/private/tmp/q04-i-retained-readonly.tar`; its digest is
in runtime-diagnosis.json. No recovered bytes replaced original controller data.

UID-fenced cleanup proved old Deployment/ReplicaSet/Pod and owned ConfigMaps
absent, scratch/children absent, terminal and post-cleanup OOM checks passed,
Temporal/object-store health passed. All 32 held Deployment UIDs remain at zero.
PVC `q04-pod-cgroup-i-evidence-20260920-i` remains Bound with UID
`40b563b4-05f2-4b86-bafb-efcb1422a296`; PV UID
`256b3fea-6362-45f9-b0d9-cd364f08c07f`. Historical PVCs/prefixes are untouched.

## Local reproduction and next decision

[The offline reproducer](../../diagnosis/yolo-pod-i-transport/reproduce_transport_stop.py)
reproduces both scratch disappearance and terminal-drain receipt gap without a
cluster. These are newly exposed remaining acceptance-tool defects, not reasons
to loosen pressure/resource/telemetry thresholds. No second runtime is planned
in this execution session. See [follow-up plan](../../diagnosis/yolo-pod-i-transport/NEXT-WINDOW.md).

The two requested H defects are fixed and locally tested; real I cleanup proves
the sealing repair. The transport contract needs another reviewed repair before
further runtime. Q04 remains unqualified and #51 must remain open.
