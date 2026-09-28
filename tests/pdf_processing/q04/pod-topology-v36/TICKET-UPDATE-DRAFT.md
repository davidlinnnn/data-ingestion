AK completed one controlled current-v3 native old-request rejection run. Fresh completed 51 pages; the identical request under a changed profile returned `failed/worker_method_mismatch`, zero registered pages and no processing result. Its Temporal execution completed with one expected non-retryable failed Activity. The retained original plan remained bound to its original profile, and replay on that route recovered the original complete processing result and exact document digest.

All 725 process/cgroup samples passed unchanged guards. The 61-file terminal inventory passed independent exact-set/hash/readback verification. Workload exit and UID-fenced cleanup passed; AK PVC is Bound and retained, and all 32 held Deployments remain off. No automatic retry or threshold change occurred.

The changed-profile old-request rejection gate is now proven. #51 remains open for evidence-only compatible reuse, real method invalidation, required-relationship interruption/retry/replay, active telemetry-loss abort, process/Pod recovery and the #44 operating-bounds handoff. No integration or closure claim yet.

Evidence: `tests/pdf_processing/q04/pod-topology-v36/first-window-evidence/RESULTS.md` and `INDEPENDENT-VERIFICATION.json`.
