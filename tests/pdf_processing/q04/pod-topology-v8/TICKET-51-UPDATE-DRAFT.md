## Q04 execution-session update — H tool repair and controlled I result

Two H acceptance-tool defects are repaired: controller/terminal samples are saved
before rejecting them, and worker marker discovery excludes sibling worker-N.log
files. Historical A–H runners, evidence, PVCs and prefixes remain unchanged.
Repair commits: 49eba63 and 41a8816; the single I run used 41a8816.

Validation: 104 offline tests passed, covering exact red/green failure reproductions,
full CLI arguments, ConfigMap-projected source and actual reviewed runtime contract,
real process interruption, failed-workload sealing and snapshot/mirror/archive
readback. Independent Standards/Spec review found one interruption-record transport
allowlist omission; it was reproduced, fixed and re-reviewed before runtime.

H diagnosis is stronger after read-only PVC recovery: worker node full avg10=.54,
cgroup PSI also positive, inner VM PSI failure invokes workflow cancellation;
outer SIGINT interrupts cleanup, then the glob defect prevents sealing. Temporal
has cancellation followed by COMPLETED/business failed, not an Activity timeout.
activity_budget_exhausted is a generic cancellation fallback here. Exact outer
rejecting sample, task-level pressure cause and full-workload capacity remain unknown.

I (q04-yolo-pod-cgroup-20260920-i) passed admission and all 11 pre-inference gates.
Fresh completed and registered the first five pages, then normal scratch removal
triggered the transport's durable-file-disappearance check. Controller interruption
canceled the next group. Result: FAIL_TRANSIENT_SCRATCH_EVIDENCE_CONTRACT; business
failed, processing_complete=false; restored/replay not started. No automatic retry.
194 controller samples: node PSI0, VM OOM0, minimum available 6,678,102,016 bytes.
Cgroup PSI reached .18; incomplete runtime does not qualify operating bounds.

The repaired cleanup sealed the failed workload with cleanup_complete=true. Its
38 terminal inventory entries were verified by exact size/SHA-256 after separate
read-only PVC recovery. Automatic controller export still failed on transient
inventory/cleanup receipt-gap handling; its original INCOMPLETE disposition is
preserved. Owned Deployment/ReplicaSet/Pod/ConfigMaps are gone; no owned Running
workflow remains; all 32 held Deployment UIDs remain at zero; all prior PVC UIDs
are unchanged. I PVC 40b563b4-05f2-4b86-bafb-efcb1422a296 is retained.

Next prerequisite is a reviewed transport repair: keep recognized parser scratch
outside the durable mirror, retain strict durable-file integrity checks, and allow
separately classified post-stop sealed forensic export without relaxing the live
5-second qualification gap. Deterministic offline reproduction is retained. Use
another new identity only after that repair; do not rerun I or change memory/PSI
standards based on this evidence.

ACL/Keynote previously proven rows remain; YOLO full fresh/restored/replay/graph,
native/WikiSkill/AIMA Q04 rows, integrated bounds/warm/drain and six-fixture matrix
remain unproven. Tool repairs and diagnosis can be integrated with these limits;
Q04 does not pass and #51 remains open.

Evidence: tests/pdf_processing/q04/pod-topology-v8/SESSION-HANDOFF.md,
first-window-evidence/RESULTS.md, and diagnosis/yolo-pod-h-stop/DIAGNOSIS.md.
