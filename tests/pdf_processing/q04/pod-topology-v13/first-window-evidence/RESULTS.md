# N: business complete, acceptance rejected

Execution `985b89a`, identity `q04-aima-pod-cgroup-20260920-n`, original
fixture 08 pages 99–110, original `max_requests=20`. One execution, no retry.
All 11 pre-inference gates passed. Fresh completed 12/12 registered pages and
9/9 selected OCR components. Temporal completed at 2026-09-20 01:30:35.189431 UTC
with a complete business result. This differs from H/L's failed business result.

The unchanged consumer rejected the full graph. The only differences are added
`image` fields on all 12 pages and 9 PictureItems; no source segment was removed
or added. Q04 binds the Q01 checkpoint-only reference, whose assembly did not
load images. The offline [source-pixel audit](../../diagnosis/aima-n/image-audit.json)
proves every added page pixel against the fixed PDF and every picture pixel
against its exact page crop. All other projected graph fields match exactly.
The audit is inactive and does not change the original rejection.

The collector also fails qualification: 2/416 process samples have unknown PSS
(indexes 395 and 414). The existing offline exit classifier confirms the exact
identities exited between complete adjacent samples, but N did not authorize
that classification. Missing PSS remains unknown. The observed warm handoff also
preceded the asynchronous workflow `assembling` query, violating the collector's
fixed observation order. A query observation is not an Activity-start timestamp.
Neither defect/limitation is silently waived.

There was no node full-PSI violation, cgroup pressure total, OOM increment, or
deadline exhaustion. Outer peak was 1,788,489,728 bytes; complete-attribution
peak was 1,785,384,960 bytes. Minimum node available was 6,294,089,728 bytes.
Maximum outer gap was 0.433764 s; attribution gap was 0.484224 s.
The consumer error caused owned cleanup; the supervisor exited 1 normally
(`forced=false`, `timed_out=false`), then the controller recorded workload failure.
No supervisor interruption initiated the business result. Restored/replay did
not run; no accepted fresh index exists.

Independent verification checked all 41 sealed inventory entries and 42 archive
files by path, size and SHA-256, including the inventory digest and byte equality
against the retained raw tree. Runtime objects were removed with UID fencing;
both persistent channels closed, terminal cgroup/VM OOM proofs passed, all 32
held Deployments stayed at zero with unchanged UIDs, and Temporal is idle.
Historical PVC UIDs are unchanged. N PVC UID
`5119fe09-0d80-4759-a83c-4976bd88dca0` and all object prefixes remain retained.

Raw graphs/archive remain in `/private/tmp/q04-aima-pod-cgroup-20260920-n` and the
retained PVC. `RAW-EVIDENCE-MANIFEST.json` binds those private artifacts; they are
not copied into Git. This is **FAIL_GRAPH_AND_ATTRIBUTION_NOT_PROMOTED**, not an
AIMA or Q04 pass. #51 is not ready for closure.
