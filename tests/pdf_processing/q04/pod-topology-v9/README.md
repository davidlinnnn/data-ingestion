# Q04 fixture 07 Pod topology v9 / J

J repairs the evidence transport failure observed in I. A–I runners, runtime
manifests and raw evidence remain unchanged. Read I's retained result and
`diagnosis/yolo-pod-i-transport/NEXT-WINDOW.md` for the starting evidence.

The live snapshot prunes only `state/<J phase>/worker-N/scratch/` directories,
where N is numeric. It does not enumerate disposable parser files as permanent
evidence. Every durable path remains subject to identity, disappearance, extent,
chunk-hash, terminal inventory and archive checks. The final seal must contain
the complete stable inventory; leftover scratch cannot silently qualify.

On failure, the controller retains the failed live mirror and its ledger. Once
supervisor absence and cleanup are confirmed, it builds an independent
`failure-evidence/` mirror, validates every sealed file plus PVC identity, and
exports a matching stable archive. `live_qualification_passed=false` remains
explicit. A successful forensic export never turns the workload into PASS.
Both live and forensic pull cadence retain the existing 5-second gap check;
no live timestamp is reset and no evidence is overwritten.

Runtime image, source producer, models, oracle, resources and deadlines are
unchanged. The unique J identity/prefix/PVC prevents rerunning I. See RUN-PLAN.md
and OFFLINE-VALIDATION.md; this preparation alone grants no acceptance.
