# T09b B3 pre-inference stop

Run identity: `t09b-calibration-20260929-b3`. One execution, no retry.

B3 passed capacity admission and ten of eleven pre-inference gates, then stopped
before workflow creation, object writes or inference. The failed gate was
`workload_imports`: `candidate_window.py` imported the B2-only
`candidate_contract`, which was absent from the B3 projected workspace.

This was an identity-projection defect, not a resource or runtime result. The
Pod had zero OOM counters; node full PSI avg10 stayed 0.00 during the outer
observation window. UID-fenced cleanup removed the B3 Deployment, Pod and source
ConfigMaps, restored all held workloads to zero replicas, and retained the Bound
evidence PVC `t09b-calibration-b3-evidence-20260929` with UID
`bb5a18b5-3605-4885-9821-657af502e662`.

B3 is not a group-10 replicate and will not be reused. The projected-workspace
regression now imports the B3 window through the exact Pod source projection; the
next group-10 cell requires a new run identity.
