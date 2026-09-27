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

The next decision is whether zero *any* cgroup full-PSI microseconds is the
intended #44 acceptance condition for the temporary object limit. Review the
BR object trace alongside the accepted workload requirement and prior object
measurements; if the condition remains, first identify a workload/environment
change that can plausibly avoid the stall, then prepare a fresh identity and
one controlled run. If the condition should instead express a sustained
pressure bound, that is an acceptance-standard change requiring a concrete
proposal before implementation. Do not repeat BR unchanged.
