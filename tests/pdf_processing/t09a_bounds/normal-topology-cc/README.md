# CC: direct-reclaim attribution under the normal topology

CC uses a fresh run identity and object prefix with the CB producer, frozen
fixtures, exact five-document workload, 29 requests, request-20 recycle, and
unchanged admission/runtime/PSI/OOM/deadline guards. The outer controller
activates the 32 recorded Deployments only for this one window, then restores
them to zero and returns object service to 512Mi. It does not retry.

A disposable local Docker container shares the kind VM's PID and cgroup
namespaces, has no network and a read-only filesystem, and records direct
reclaim begin/end tracepoints in its own tracefs instance. This is necessary
because tracepoint PIDs are VM host PIDs, while `/proc` inside a kind node
uses a different PID namespace. The tracer is removed after the window.

Local checks passed for the exact runner command, source projection,
pre-inference configuration and imports, cleanup markers, guard interruption,
and one-second tracer startup/cleanup. See `first-window-evidence/RESULTS.md`
for the failed runtime result and its limits.
