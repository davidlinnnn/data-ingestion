# J result — FAIL_ATTRIBUTION_CONTRACT_NOT_PROMOTED

Executed repair commit **2619844** once, with identity
`q04-yolo-pod-cgroup-20260920-j` and prefix `q04/yolo-pod-cgroup-20260920-j/`.
All 11 pre-inference gates passed. No retry or threshold change occurred.

## What passed and what did not

Fresh, restored and exact-fresh replay each completed their business workflow,
registered 15/15 pages and produced `accepted.json` with `verified=true`.
All three histories contain 11 completed Activities and no Activity failure,
timeout or cancellation event. The source-reviewed, content and full-reference
checks are retained in each case directory. These are successful bounded case
checks inside an **unqualified window**, not a promoted Q04 acceptance index.

The matrix then failed `candidate qualification evidence incomplete` at
`candidate/yolo_reviewed_candidate_window.py:165`. The measurement contract
records `workload_succeeded=true` but `qualification_complete=false`,
`process_attribution_complete=false`, and `cgroup_resource_complete=false`.
Fresh index and phase-complete records remain `.pending.json`; no promotion.

## Causal chain and measurement evidence

1. Three workflows finish successfully; worker generations shut down normally.
2. Collector finalization finds **54 incomplete samples out of 1,023**.
3. Qualification assertion raises; matrix exits 1; supervisor writes workload
   exit at epoch 1789862326.4367075 (`timed_out=false`, `forced=false`).
4. Outer controller observes failed workload at 1789862326.6651578, retains the
   primary error and executes the independent stopped forensic export.
5. Seal/archive verification completes before UID-fenced owned runtime removal.

There is no PSI-triggered cancellation, Activity budget exhaustion or supervisor
interruption in this J causal chain. Compare H and I in the prior handoff: H was
PSI-triggered cancellation with missing exact outer sample; I was scratch
transport failure followed by interruption/cancellation.

The 54 incomplete rows include 35 process reads with `PermissionError`, all
`shared_cgroup_other`, same command SHA256
`d1750f4987f0f1657c272aa5bad1b18d9f13b8ef307c789460b006ee2fdb9fe3`.
Six process reads report `FileNotFoundError`. Coverage reasons also include
process-set changes and process-identity read races. Counts overlap and must not
be added as disjoint sample counts. The collector records neither the failing
filename nor errno; `_read_process` groups status/smaps reads in one handler.
The exact helper identity and cause of PermissionError remain **unknown**.
Short-lived monitoring/exec processes are a hypothesis, not a proven exemption.
Missing PSS cannot be replaced with zero or inferred from neighboring samples.

The 681 outer samples have node full avg10=0, no VM OOM, minimum available
6,570,520,576 bytes (6.12 GiB), maximum cgroup 1,725,132,800 bytes. The attribution
stream has cgroup full avg10=0, OOM counters zero, maximum memory.current
1,768,689,664 bytes (1.65 GiB), maximum gap 0.408 seconds. Parser recycle/exit
contract is complete and no warm/fresh overlap is observed. These measurements
exclude a sampled pressure/limit breach as the stop trigger; incomplete process
coverage still prevents an accepted integrated resource bound.

## Repair validation in live runtime

Normal worker scratch creation/removal no longer appears as durable evidence
loss. All **115 live transport receipts** remained within the unchanged 5-second
gap (maximum **2.703 seconds**). Failed-workload export used a separate forensic
mirror, retained live qualification failure, and returned
`FAILURE_EVIDENCE_RETAINED`. Its two pulls captured all 77 sealed inventory entries.
Independent readback confirms exact files, sizes, SHA256 and byte-for-byte tar
agreement, including the terminal manifest. No separate PVC rescue was needed.
The terminal seal stays `INCOMPLETE`; export success does not promote it.

## Cleanup and retained evidence

All owned runtime objects were removed with UID preconditions; owned worker,
parser, scratch and emptyDir absence are proven. No J Running Temporal execution
remains; service health is idle. All 32 exact held Deployment UIDs remain at zero.
All historical PVC UIDs are unchanged. J PVC
`7dfaf208-979b-4d20-87d1-74f5bc158ea6` and PV
`6390ee64-134e-4d9e-9f20-217fc418a961` remain retained; object prefix is preserved.

Raw live mirror is `evidence/`; complete stopped mirror is `failure-evidence/`.
See `runtime-diagnosis.json`, `temporal-reconciliation.json`,
`independent-evidence-verification.json`, `outer-cleanup.json`, and
`post-run-readonly.json`. All original runtime bytes, including the early
ownership-file publication race logged during startup, are preserved. That
startup probe was retried within the runner, did not stop the run, and is not a
workload/window retry.
