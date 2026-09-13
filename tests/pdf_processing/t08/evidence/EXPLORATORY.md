# Unqualified exploratory runs

The initial baseline request `t08-red-missing-routing` lacked any frozen route but
reached the legacy Activity, which reported `invalid_request`. The required
`invalid_routing` assertion failed. This is the saved red test.

Initial image setup confused Kubernetes runtime config imageID with the OCI
manifest digest. No method execution was accepted on that image reference; the
harness now uses the verified containerd manifest and a separate T08 digest alias.

The first rollout driver used `.name` on a protobuf integer enum; corrected to
`EventType.Name`. A subsequent run completed its queued request but the host's
`kubectl exec` stream and cleanup API calls timed out. It is excluded from rollout
and timing acceptance. An unintended broad Pyright scan consumed approximately
4GB host RSS and was stopped; this observation does not establish the sole outage
cause. T09a also reported API availability problems.

Both tasks paused and independently confirmed worker quiescence under the shared
recovery flock. T08's only remaining Pods were client-only coordinator, objects and
Temporal. No T06/T07 or unrelated worker was stopped. The controller now retains its
lock through API errors and cleanup retries until owned remote worker Pods disappear.
No per-scenario inference Worker runs in the T08 coordinator.

A later attempt copied the updated package into a nested directory in coordinator,
so the client saw the previous `submission` signature. It failed before inference;
cleanup verified all worker Pods absent. Package transfer now replaces the owned
client-only directory with exact source files.

The next run passed queued work and injected native parser loss, but inherited
256Mi-per-Pod reservations left new workers and the old Workflow replacement
Pending/Insufficient memory. It was interrupted and excluded. The locked cleanup
waited until even the unscheduled Pods disappeared. The final harness uses
qualification-only group256Mi/other64Mi reservations while preserving 5Gi limits
and frozen processing budgets; these do not establish calibrated resource bounds.

With scheduling corrected, a warm one-page parse finished in about 1.2 seconds
between the native-stage observation and rollout API calls. The required attempt2
assertion failed despite a complete correctly attributed result; that trial is
not loss/retry evidence. The final controller tracks unmatched stage-enter events
and SIGSTOPs the live child inside the same probe before any rollout command,
then exercises forced loss and bounded graceful drain. Inference is real and no
production collaborator is replaced; this qualifies interruption of a paused
active parser, not a claimed exact neural instruction.
