# AO node PSI source: unresolved, measurement seam confirmed

The retained 250 ms controller samples show node `full` stall time rising from 15:40:00.830 UTC, while `full avg10` remained 0 until the 15:40:02.364 trigger sample reported 1.08. From ten seconds before the trigger, node stall time rose 153,818 microseconds and the AO Pod cgroup stall time rose zero. The node still had 5.57 GiB available, the AO Pod was at 1.84 GiB of its 5 GiB limit, and no OOM counter increased. Temporal cancellation followed the controller stop; the required-evidence injection was not reached. These records establish the stop sequence, but neither prove AO caused pressure elsewhere nor identify another process as its source.

Ranked, falsifiable explanations for the next observation:

1. Another Pod or node service stalled on memory. Its cgroup `full total` should rise with node `full total` while AO's does not.
2. AO's allocations indirectly caused other workloads to stall. The same external cgroup deltas should coincide with AO's rising memory charge and Activity onset, but this observation alone cannot prove causation.
3. Pressure occurred outside the kind-node cgroup subtree or in kernel work. Node `full total` would rise without matching deltas in any cgroup visible from the kind node.

The existing kind worker2 exposes 68 readable `memory.pressure` files, including system, kubelet and Pod cgroups. A five-second idle, read-only run of [node_pressure_attribution.py](../../sentinel/node_pressure_attribution.py) completed with a 250 ms interval: 68 cgroups at start/end, no node or cgroup `full` increase. This validates access and bounded collection, not any AO event attribution. `/proc/pressure/memory` and the visible cgroup root have different cumulative totals, so a node increase with no visible cgroup increase must remain **unattributed**, not assigned to a specific process.

For a later new-identity relationship attempt, start this probe before workload admission, retain its JSONL through terminal cleanup, and correlate node/cgroup deltas with the existing controller, Temporal and AO Pod samples. Keep the zero node PSI guard and all other thresholds unchanged. A quiet pre-admission period alone is insufficient: AO's pressure began after fresh completion despite passing pre-admission gates. Do not reuse AO's identity, prefix or PVC, and stop on the first guard failure.
