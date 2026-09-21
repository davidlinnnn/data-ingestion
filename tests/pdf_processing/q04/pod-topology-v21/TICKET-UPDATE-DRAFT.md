Q04 warm runtime V (`q04-warm-pod-cgroup-20260921-v`) ran once without retry.
All 11 pre-inference gates passed, but init stopped before any workflow,
Activity, parser or inference because the retained input bundle still bound the
pre-repair telemetry and regression-test hashes. A read-only recovery of the
retained PVC preserved the exact init traceback and sealed cleanup evidence.

No PSI, OOM, memory-floor or deadline gate fired. Owned runtime and the recovery
helper were removed with UID fencing; the V evidence PVC remains Bound and all
32 held Deployments remain off.

The defect is in preflight parity: it checked the bundle's inputs hash but did
not run `verify_bundle()`, while init did. W adds that exact preflight check and
uses a new bundle with only the two reviewed harness hash changes. Sources,
oracles, producer and resource thresholds are unchanged. V is failed and will
not be reused. #51 remains open.
