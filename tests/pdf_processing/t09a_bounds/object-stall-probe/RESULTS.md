# Minimal object-read diagnostics

CE observed 45 seconds with all 32 held Deployments off and object at restored
512Mi. Direct function tracing captured PSI memory-stall entry callers and
live task cgroups, but no target MinIO stall. This does not reproduce CD.
CE exposed a diagnostic cleanup defect: switching current_tracer while the
trace_pipe fd was open returned EBUSY. The exact private instance was then
removed; the tracer now closes the fd before switching to nop. CF and the CG
one-second start/end check verified the corrected real cleanup path.

CF performed one bounded, read-only sweep of the preserved CB object prefix
through the existing coordinator. It read 27,377,764 bytes within the 30-second /
32MiB bound, with no retry, no object mutation and no target object PSI increase.
The direct-caller tracer exited cleanly. No deployment replicas or resource
limits changed. Two local attempts before CF started stopped at import time;
no remote work occurred. The final script uses the coordinator's installed
client rather than installing a new dependency.

A standalone read does not reproduce the mixed-load failure. The next
measurement (CG) keeps CD's workload/guards and replaces broad MinIO
sched stacks with direct psi_memstall_enter stacks and task cgroups.
