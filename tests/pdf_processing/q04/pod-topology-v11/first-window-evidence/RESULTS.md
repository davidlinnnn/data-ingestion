# L result — real pressure stop, complete process measurements

Executed source `10b4723`, identity `q04-yolo-pod-cgroup-20260920-l`.
11 pre-inference gates passed. Fresh 07 failed before any registered page;
restored and exact replay did not run. No retry. Q04 and #51 remain unqualified.

At 00:38:34.681 UTC the cgroup first recorded direct reclaim (448 pages),
53,668 microseconds pressure total and ~890 MiB anon THP. At 34.935806 the saved
rejecting sample showed node full avg10 0.36, 6,486,183,936 available bytes,
1,741,189,120 cgroup bytes, 2,496 directly reclaimed pages and 62,028 microseconds
cgroup pressure. OOM/high/max counters stayed zero. Cgroup avg10 was still zero;
its nonzero total prevents interpreting that as no pressure. Sampling is not
atomic across node/cgroup files.

Controller recorded stop at 34.936881 and supervisor signal at 35.041423.
Temporal cancel request was recorded at 35.156261, workflow completed at
35.171374 with business failed/activity_budget_exhausted, processing_complete
false and zero registered pages. There are no Activity timeout events. Worker
trace reports CancelledError; inner guard traceback is VM PSI pressure.
Supervisor records KeyboardInterrupt at 35.298100. These prove overlapping
pressure-triggered cancellation/interrupt cleanup, not an exhausted time budget.
Worker log has no timestamp proving exact ordering of its cancellation against
the outer signal. Missing such ordering remains unknown.

All 290 process samples were complete, no unclassified reads, maximum gap
0.345449 seconds. The L observer fix works over this interval, but qualification
remains false because the run stopped before required lifecycle observations.
The post-stop vmstat shows compaction history but lacks trigger-time deltas;
THP-related compaction is a hypothesis, not a proven root cause.

Independent verification matched all 38 sealed inventory entries by size/SHA256,
the inventory digest, exact tree membership, and all 39 tar file bytes. Automatic
forensic export succeeded, both channels closed, owned runtime removed with UID
preconditions, all 32 held Deployments unchanged at zero, Temporal idle. L PVC
cbeb23ec-5f95-459e-add9-ec698d72b5ae and all historical PVCs/prefixes remain.
Terminal cgroup sample was saved but failed the PSI validator; cleanup records
terminal_cgroup_oom_proof=false. The separate post-cleanup VM OOM proof passed.

See temporal-reconciliation.json, runtime-diagnosis.json, outer-cleanup.json,
independent-seal-verification.json and post-run-readonly.json for raw evidence.
