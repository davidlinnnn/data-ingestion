# Draft only — not posted to #51

H's dropped stop sample and worker-log cleanup defects are repaired and tested;
historical evidence is retained. H/L stop histories show PSI-triggered
cancellation, not demonstrated Activity deadline exhaustion. The generic
`activity_budget_exhausted` result must not be read as an actual timeout.

M (`d1701d3`) passed bounded YOLO07 fresh/restored/exact replay, the approved
two-pair graph equivalence, all 1,021 complete process samples, unchanged resource
guards and cleanup. Scope remains fixture07 with max_requests=1 and THP disabled
for workload descendants. One pass does not prove THP caused L's earlier PSI.

N (`985b89a`) used original AIMA08 max_requests=20 and completed 12 pages plus
9 OCR components, then failed the original full-graph gate. Its 21 added image
fields are explained by Q01's image-free checkpoint-only reference; an inactive
pixel audit matches every image to the fixed source and all other graph fields
exactly. Two unknown PSS exit samples and an asynchronous query-order condition
also prevent measurement qualification. Restored/replay did not run; no retry
or fresh-index promotion occurred. Node/cgroup pressure and OOM remained zero.

N's 41 sealed entries/42 archive files are independently verified. Owned runtime
objects are gone, all 32 held Deployments retain UIDs/zero replicas, Temporal is
idle, and all historical PVCs plus N's evidence PVC/prefix are retained.

Local validation: N 131 focused tests and 32 relevant consumer/controller tests
passed. The broader 702-test attempt did not pass; missing historical inputs,
dependency/sandbox issues and the superseded matrix assertion are documented in
OFFLINE-VALIDATION.md. The new real-N image audit and seven negative mutations
pass while explicitly retaining the original consumer rejection.

Q04/#51 remains open: six-fixture/current-producer matrix, original cross-document
request20 warm behavior, invalidation/old-profile rejection and interruption /
telemetry / process / Pod recovery still require evidence. No standard is changed
without explicit adoption of the concrete proposal. No push or issue publication
has been performed in this session.
