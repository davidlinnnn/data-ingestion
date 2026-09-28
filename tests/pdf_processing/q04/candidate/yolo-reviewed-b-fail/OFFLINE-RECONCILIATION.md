# YOLO reviewed-B offline reconciliation

The `yolo-reviewed-b` runtime remains `FAIL_ATTRIBUTION_CONTRACT_NOT_PROMOTED`.
This reconciliation neither edits its archive nor promotes its pending index.
Its immutable raw archive is 26,316,800 bytes with SHA-256
`54a78e7cea4bde77e85ada57ac106f93c7b53cf53192c0fb18b0c192b26091af`;
the retained replay records run
`q04-7f83ffd09dbc4db2b4891282826a622a` and exact source samples 725–727.

The offline harness now separates two questions. The cgroup resource gate uses
complete `memory.current`, `memory.events`, `memory.stat`, pressure and timing
readings. Process PSS attribution remains incomplete when a process disappears
during `/proc` reads. The latter is never replaced with zero, interpolated or
reported as complete.

Sample 726 can be classified only as a confirmed-exit transition for cgroup
qualification. Samples 725 and 727 bound it within the collection interval;
PID 5038 has the same start ticks and cgroup identity before the failed read,
the failure is `ProcessLookupError`, the next enumeration omits that identity,
and the retained stream contains its exact exit event. Sample 726 remains
`attribution_complete=false` with unknown PSS. PID reuse, permission denial,
an unknown descendant, a peak-sample gap, an incomplete cgroup read, missing
identity or missing exit proof all fail closed.

For `max_requests=1`, the accepted fresh record's three
`termination_reason=request_recycle` labels are claims rather than exit proof.
The harness now requires distinct parser identities and an observed exit for
each before assembly. It rejects a label without an exit and any warm parser
present at assembly. The handoff marker is required only when a live warm parser
actually reaches a handoff boundary.

The fixture graph, fresh/restored/exact replay equivalence, PSI/OOM readings and
cleanup from the historical run are preserved. The observed peak was
4,285,693,952 bytes, only 9,273,344 bytes (8.844 MiB) below the unchanged 4 GiB
guard, so this replay does not establish a reusable capacity margin. A future
runtime is not automatic: main should first decide whether that margin is
acceptable or whether fixture 07 needs a dedicated cgroup or Linux host. If
live proof of the corrected collector is still required, use one new identity
and the same fixture-only scope, thresholds, no-retry rule and cleanup contract.
