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
