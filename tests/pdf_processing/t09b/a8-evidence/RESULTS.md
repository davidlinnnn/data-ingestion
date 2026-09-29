# T09b A8 pre-workload stop

Run identity: `t09b-calibration-20260929-a8`. One execution, no retry.

A8 passed the 60-second capacity admission, then stopped during preflight before
workflow creation, object writes or inference. The projected workspace contained
the A8 wrapper but not its A7 wrapper dependency, so `pod_preflight_a8.py` raised
`FileNotFoundError` for `pod_preflight_a7.py`.

This was a harness source-projection defect, not a group-5 runtime result. The
workload remained `NOT_STARTED`; the admission sample reported zero OOM, node
full PSI avg10 0.00, and at least 5,335,699,456 available bytes. UID-fenced
cleanup removed the A8 Deployment, Pod and source ConfigMaps, restored all held
workloads to zero replicas, and retained the Bound evidence PVC
`t09b-calibration-a8-evidence-20260929`.

A8 is not a group-5 replicate and will not be reused. A8 wrappers now read the
projected base templates directly, and the regression executes them from a
workspace containing only the rendered Pod projection. The next group-5 cell
requires a new run identity.
