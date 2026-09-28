Draft for #51; **not posted**.

The Q04 H stop was a node-memory PSI guard cancellation, followed by a failed
business result; Temporal `COMPLETED` did not mean ingestion succeeded. The
triggering sample was lost by the old controller and `worker-1.log` broke
terminal cleanup. Both acceptance-tool defects have regression tests and are
fixed. The exact H trigger remains unavailable, so its capacity cause is not
claimed. Historical A–AG evidence remains untouched.

Source review rejected the v1 native graph: five of six changed components
contained invalid cross-page reading-order joins. The v2 adjacency fix
removed the six v1 cross-page edges, but offline AIMA projection exposed a
valid continuation across a page-margin picture. V3 limits that exception to
pictures outside the body text span. All 38 native/Wiki06 splits were source-reviewed, and a strict
exact-graph oracle rejects any unreviewed change. Six fixture captures under
the pinned image passed local checks; code review cleared the final v3 change
and the AH runtime adapter. Relevant code commits are `f46f511` and `b8174f5`.

AH ran once on the existing kind cluster with a new identity/prefix, unchanged
guards, and no automatic retry. Outer admission and all 11 pre-inference gates
passed. Five real Temporal workflows completed with full durable consumer
verification: Wiki06 (twice), YOLO07, AIMA08 and native 51 pages each match
their frozen v3 graph and document digests. The two Wiki06 warm documents are
byte-identical. The 29-group sequence and request-20 parser recycle passed;
all 1,349 process/cgroup samples were complete with zero PSI, OOM or memory
violations. The 93-entry terminal inventory passed independent SHA-256
readback. Workload and controller exited zero; owned Pod/Deployment/ConfigMaps
are gone; the AH evidence PVC remains Bound; all 32 held Deployments remain
exact/off. Raw evidence is retained under
`/private/tmp/q04-warm-pod-cgroup-20260924-ah` and the AH PVC. The reviewed
summary is `tests/pdf_processing/q04/pod-topology-v33/first-window-evidence/RESULTS.md`.

This qualifies the v3 warm sequence, exact graph checks and integrated
resource bounds only. Standalone v3 fresh/restored/exact-replay outputs and
their equality with AH warm output are still unproven. Changed-profile
rejection, current process/Pod interruption recovery, telemetry-loss
injection and the #44 bounds handoff also remain open. #51 is not ready to
integrate or close. The next controlled execution should be the v3
fresh/restored/exact-replay matrix with a new identity and the same fail-stop
policy.
