# Post-DC readiness correction

The DC run used `ff57ee9` and failed before workload. Its runner and manifests
are retained unchanged. The correction is in the shared new deployment-policy
helper, after that execution.

`python3 -B tests/pdf_processing/t09a_bounds/test_object_policy.py`

- Before: `test_container_ready_waits_for_minio_service_ready` FAILED,
  `AssertionError: 0 != 3` (the old helper never queried HTTP readiness).
- After: all5 deployment-policy tests PASS, including delayed Service readiness
  and persistent-not-ready deadline. The original retain/restore/concurrent
  change cases still pass.
- Actual read-only coordinator check against restored MinIO PASS: the corrected
  helper returned the existing512Mi Pod only with Service HTTP200.
- Complete necessary regression suite:14 tests,13 PASS on macOS and1 Linux-only
  skip. The skipped missing-start observer cleanup was separately executed on
  the actual Linux node and PASS. Syntax/whitespace checks PASS.
- Standards and Spec review of the correction:0 unresolved findings each.

No new rollout, workload or automatic runtime retry was performed. The native
object candidate remains unqualified; a future qualification needs a new
identity. No production source, resource threshold or deadline was changed.
