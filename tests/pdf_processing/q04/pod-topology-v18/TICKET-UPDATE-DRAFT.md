# #51 update draft — not published

Controlled execution S (`78063af`,
`q04-warm-pod-cgroup-20260921-s`) ran once. Outer admission and the repaired
Deployment identity gate passed; the worker Pod became Ready. Its first
pre-inference command then failed because the projected workspace omitted the
transitive dependency `pod_preflight_q.py`.

No workflow, Activity, workload or inference started, so S provides no
ingestion or warm-sequence acceptance result. Source-manifest membership proves
this was an acceptance-harness projection defect. PSI, OOM and capacity did not
cause the stop; workload capacity remains unmeasured.

Cleanup removed the Pod and all S runtime objects with UID preconditions. The
evidence PVC remains Bound and retained. All 32 held Deployments remain exact
and off; Temporal is healthy and idle; object health is 200; post-cleanup node
PSI/OOM are zero.

T uses a new identity and includes the complete transitive preflight source.
Its regression reconstructs the exact ConfigMap-projected workspace before
importing the preflight, closing the test gap that let S pass locally. Automatic
retry remains disabled and all thresholds are unchanged. S will not be retried;
T remains unexecuted pending new explicit authorization after the fail-stop.

Q04 remains partially accepted only at the previously recorded bounded rows.
The original 29-group request-20 sequence and remaining matrix/recovery gates
are unproven, so #51 is not ready to close or integrate.
