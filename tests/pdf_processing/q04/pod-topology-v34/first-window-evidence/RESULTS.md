# Q04 AI bounded matrix result

**PASS for current-v3 Wiki06/native fresh, restored, exact replay and AH warm
equality only. #51 remains open.** One controlled execution used
`q04-matrix-pod-cgroup-20260924-ai` and prefix
`q04/matrix-pod-cgroup-20260924-ai/`; no automatic retry or threshold change
occurred. [Machine verification](INDEPENDENT-VERIFICATION.json) records the
six histories, exact digests, resource gate and sealed inventory.

The outer 60-second admission passed with 48 samples, zero resets, zero full
PSI, unchanged OOM and at least 7,467,843,584 available bytes. All 11
pre-inference gates passed. The source/producer/profile/method matched the
frozen AH v3 bundle; the new prefix was empty before initialization.

| Fixture | Fresh | Restored/new request | Exact replay | AH warm equality |
| --- | --- | --- | --- | --- |
| Wiki06, 28 pages | complete, 6 groups fresh | complete, 6 groups reused | complete, same request and processing result | exact document SHA `5f00af22…e28404cb68` |
| native, 51 pages | complete, 11 groups fresh | complete, 11 groups reused | complete, same request and processing result | exact document SHA `70673bdc…c6af9f152` |

All six Temporal histories ended `WORKFLOW_EXECUTION_COMPLETED`, with no
ActivityTaskFailed events. All six business results had
`processing_complete=true`, full registered-page counts, and no business
error. For each fixture, restored used the same versioned source artifact and
a new request/result identity; exact replay used the original request and
processing result. All six documents were byte-identical within their
fixture and equaled AH's reviewed warm document digest. Their full graph
digests matched the frozen v3 oracle: Wiki06
`8f3a24bf…965497b6b0`, native `9f1b0ef9…f4d94972`. The consumer re-read
durable selections, OCR, typed graph and source evidence before acceptance.

The strict collector retained **1,217 complete process/cgroup samples**,
maximum gap **0.741475 s** (limit 1 s), no incomplete sample, no PSI/OOM or
4 GiB cgroup violation. The independent all-sample gate passed, including
the final cleanup markers. Outer VM telemetry had 1,261 samples, at least
4,821,405,696 available bytes and maximum cgroup use 2,566,950,912 bytes.
No memory floor, OOM, PSI or deadline stop occurred.

The workload exited 0. A 102-entry terminal inventory covering 121,129,412
bytes passed independent full-file SHA-256, exact-file-set and inventory
readback; the terminal manifest is `PASS_CANDIDATE`. Owned worker, Pod,
Deployment and ConfigMaps were removed with UID checks. The evidence PVC
`q04-pod-cgroup-ai-evidence-20260924-ai` remains Bound with UID
`37cdb44c-9153-40bf-881a-859a8933d62f`; the object prefix and all
historical evidence are retained. A post-run read-only check confirmed the
32 held Deployments still have their recorded UIDs and zero replicas.
`terminal_stop_proven=false` in outer cleanup means no controller-initiated
stop was needed after normal completion; it is not a cleanup failure.

AI proves the two missing current-v3 fixture matrices and their AH warm
equality. It does not prove current-v3 YOLO/AIMA fresh equality, ACL/Keynote
current-producer applicability, changed-profile rejection, active sampler
loss, or in-flight process/Pod recovery. The complete warm and #51 release
gates therefore remain unproven.
