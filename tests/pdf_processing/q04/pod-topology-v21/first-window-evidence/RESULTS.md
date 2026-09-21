# V — preflight passed; stale bundle binding stopped init

Execution commit `68430db`, identity
`q04-warm-pod-cgroup-20260921-v`, ran once with no automatic retry. Outer
admission, Pod readiness and all 11 pre-inference gates passed. `pod_init_p`
then rejected the retained Q bundle before workflow or inference because its
harness inventory still bound the pre-repair telemetry and regression-test
hashes. No Temporal workflow, Activity, parser or inference started.

The controller initially classified workload evidence as not started because
the supervisor exited before incremental transport established ownership. A
separately recovered read-only PVC inventory proves the supervisor started,
init returned 1 with `bundle harness drift; prepare a new bundle`, cleanup found
no worker or owned child, and the durable terminal manifest sealed the failure.
This corrects evidence classification; it does not turn V into a pass.

V reached only 131,747,840 cgroup bytes in two controller samples. Terminal
node/cgroup full PSI and OOM were zero, with 7,659,966,464 bytes available.
Owned Deployment, Pod and ConfigMaps were removed; the evidence PVC
`q04-pod-cgroup-v-evidence-20260921-v` (UID
`efb941de-4307-4fbe-9b83-7e27a61c9cf1`) remains Bound. The read-only recovery
Pod was deleted with UID precondition, and all 32 held Deployments remain off.

Root cause: the V preflight verified only the stale bundle's self hash. It did
not run the same `verify_bundle()` harness binding check used by init. W adds
that preflight check and uses a new bundle containing only the two reviewed
harness hash updates; producer, PDFs, originals, oracles and reference graphs
are unchanged.

Disposition: **FAIL_STALE_BUNDLE_HARNESS_BINDING_BEFORE_WORKFLOW**. V proves no
acceptance row.
