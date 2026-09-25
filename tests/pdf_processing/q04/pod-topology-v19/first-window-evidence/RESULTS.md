# T — workload completed; warm harness stopped on pending Wiki graph review

Execution commit `d555d29`, identity
`q04-warm-pod-cgroup-20260921-t`, ran once with no automatic retry. All outer
and Pod-local pre-inference gates passed, and the workload reached the first
WikiSkill 06 workflow.

Temporal completed the workflow normally: all 21 Activities completed, 28/28
pages and 11/11 selected components were registered, and
`processing_complete=true`. No Activity failed or retried. The consumer then
stopped the warm phase because the current graph hash differed from the retained
reference while the full delta had not been source-reviewed. The graph-delta
record has no removed or added source segments. This is a harness scope mismatch:
the run was authorized to measure the fixed sequence, request-20 recycle and
resources while explicitly leaving Wiki/native fresh-output equality unproven,
but the harness required full fixture graph acceptance before continuing.

The run did not hit a PSI, OOM, memory-floor or deadline stop. The terminal Pod
cgroup sample had 7,657,279,488 available node bytes, zero node/cgroup full PSI,
zero VM/cgroup OOM and 109,744,128 cgroup bytes after the worker stopped. The
completed Wiki processing steps observed parser PID 131, one generation, no
forced kill and peak parser RSS 1,959,904 KiB. These measurements cover only the
first fixture and do not prove the 29-group sequence or request-20 recycle.

Cleanup stopped the worker and parser, proved scratch absent, scaled and removed
the owned Deployment and Pod, deleted both ConfigMaps with UID preconditions, and
retained PVC `q04-pod-cgroup-t-evidence-20260921-t` (UID
`f7e515cc-3f59-4b1e-a8d6-ce1c02eefc2f`) Bound. Post-cleanup node PSI/OOM were
zero and object health was 200.

U separates measurement eligibility from fixture acceptance. It permits a
pending graph only when source-region text, text metadata/original text, complete
picture/table/key-value/form payloads, and page payloads remain equal. It writes
`NOT_ACCEPTED_WARM_MEASUREMENT_ONLY`; Wiki/native fixture acceptance and fresh
equality remain unproven. Regression tests reject text, table-cell and
provenanced-picture changes.

Disposition: **FAIL_ACCEPTANCE_HARNESS_SCOPE_MISMATCH_AFTER_FIRST_WORKFLOW**.
T proves the first Wiki workflow completed without resource stop, but proves no
warm-sequence acceptance row and must not be retried.
