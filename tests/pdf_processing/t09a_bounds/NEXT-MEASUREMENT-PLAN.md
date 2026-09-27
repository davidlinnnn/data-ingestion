# Next normal-topology measurement after BQ

BQ executed once and stopped on node full PSI 0.18 during the first warm workload. The exact BQ worker cgroup also recorded full PSI, but the source of the entire node event remains unknown. The outer controller sent a second interruption after the runner recorded its own guard stop; terminal sealing did not finish. Preserve BP and BQ evidence. No automatic retry.

Before another runtime:

1. The BR outer-controller candidate now detects a fresh, runner-owned `controller-stop.json` and gives bounded cleanup time without a second SIGINT. If the runner has not stopped, it retains the outer guard's SIGINT and finite force deadline. A local process regression passed both branches, including a delayed terminal write. Integrate it with a complete BR runner before runtime. This is a cleanup fix, not a guard relaxation.
2. Keep BQ's incomplete-marker sealing and failure-only evidence export checks. Verify the whole interruption-to-export path with a local simulated stop, including `workload-exit.json`, `cleanup-complete.json`, an `INCOMPLETE` terminal manifest, and exported failure evidence. Never classify these as workload success.
3. For a fresh run ID, prefix, outputs and PVC, prepare the complete projected source and exact command. Keep the same 32-Deployment normal topology, fixed workload, 1 GiB temporary object-service observation, unchanged node PSI/OOM/memory floor, Pod cgroup checks and deadlines. Reuse the read-only half-second node/cgroup PSI observer; it added no pressure event during admission and identified the BQ worker cgroup at the trigger.
4. Review the diff, pass the local projection and cleanup tests, and check live cluster identities before starting one controlled runtime. Stop on any existing guard breach, never retry automatically, restore all 32 Deployments to zero and object service to 512Mi, and retain evidence. Verify restoration independently.

A repeated PSI stop remains an acceptance failure even with spare MemAvailable. A clean run must satisfy the full existing workload and evidence matrix; the temporary 1 GiB object limit still needs sustained evidence or an explicit acceptance decision before it becomes permanent. Keep #44 open.

## After BR

BR was executed once. It fixed the BQ terminal-evidence loss: runner-owned
stop, complete cleanup markers, durable `INCOMPLETE` manifest, and finalized
failure export are all present. Three warm segments completed; native was
cancelled when the object-service cgroup full-PSI total rose by 9 microseconds
with no max/OOM event and memory.current about 511MB of 1GiB. The existing
zero-event guard correctly stopped the run. No retry or threshold change.

The live #44 candidate explicitly requires zero full-PSI violations. BR's
9-microsecond object-container event is independently visible in the node
observer and fails that rule. Do not repeat BR unchanged or raise the object
limit merely because it stopped: BR used only about half of 1 GiB, had no
max/OOM event, and the cause of its cgroup stall is not isolated.

Before another runtime, choose and document one materially different, feasible
operating configuration for the existing cluster. In particular, inspect the
worker2 placement and storage constraints before proposing any relocation;
the current object Deployment is pinned there and uses PVC `object-data`.
Keep the existing zero-PSI/OOM guards unless #44 explicitly adopts a new
criterion. A new configuration needs a fresh identity/prefix, one controlled
window, failure stop, and restoration proof. BK remains the proven isolated
case; normal 32-Deployment operation remains unqualified.

## After BU

The distinct worker1 placement was tested. BS and BT stopped on inherited
node-identity checks before inference; each defect has a focused local
regression and historical evidence remains intact. BU passed those checks,
admission and all 11 pre-inference gates, but stopped during first Wiki 06
when the exact object-container cgroup accumulated full PSI on worker2. Its
object memory peaked below 0.3 GiB of the temporary 1 GiB limit, with no
max/OOM event. Failure evidence sealed and the cluster was independently
restored. Moving only the Q04 worker off worker2 therefore did not qualify
the 32-Deployment topology.

Do not launch another unchanged full workload or raise the object limit based
on BU. The next useful work is a decision on the supported operating scope:
BK proves the fixed serial workload only with the 32 historical Deployments
held off and a temporary, observed 1 GiB object limit; BR and BU show that
the all-on state fails the existing zero-full-PSI gate in two worker
placements. Treat all-on operation and permanent object sizing as
unqualified until a specific alternative configuration addresses the
observed node2/object pressure and passes the same guards. Keep #44 open and
publish the measured boundary through the normal mainline review; no
additional runtime is justified by these results alone.
