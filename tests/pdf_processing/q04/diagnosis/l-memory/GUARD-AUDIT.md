# Guard audit after L

| Contract | Measurement and purpose | L interpretation |
| --- | --- | --- |
| Node PSI | `/proc/pressure/memory` full avg10; zero required during admission/runtime. Captures host-wide stalled runnable tasks, not free capacity. Outer samples every 250 ms; worker guard separately polls. | Exact rejecting 0.36 now saved. Shared-node metric alone cannot identify causal process. |
| Pod cgroup PSI | `memory.pressure` raw some/full averages and totals in outer and attribution samples. Final all-sample gate requires full avg10 zero. | avg10 zero at outer trigger but total increased to 62,028 us. Different read/update timing; not evidence of zero pressure. |
| OOM | Node vmstat oom_kill baseline; worker cgroup memory.events oom/oom_kill/oom_group_kill zero required. | No observed increments. OOM absence does not prove no reclaim/compaction. |
| Memory floor | Outer 4.5 GiB continuously 60s before admission; case 3 GiB/60s. Runtime node available >=1.5 GiB. | Trigger available6,486,183,936 bytes. MemAvailable estimates reclaimable capacity, not contiguous hugepage availability. |
| Cgroup budget | Sampled memory.current <=4 GiB qualification; Kubernetes hard limit5 GiB. Includes descendants/cache/kernel overhead, not only parser RSS. | Trigger1,741,189,120 bytes. No high/max events. A limit rejection was not the observed stop. |
| Measurement coverage | 250 ms collector; max gap1s; complete PSS classification and final owned cleanup labels. Evidence every2s, receipt gap<=5s. | 290 process-complete samples, maxgap0.345449s; lifecycle incomplete because pressure canceled first group. |
| Deadlines | Total1500s; admission observation180s; workload825s with bounded drain; cleanup300s. Per-trial180s; parser startup120s/no-progress180s/terminate5s/reap5s. | No Temporal timeout event. activity_budget_exhausted is the cancellation fallback business code, not demonstrated duration exhaustion. |

No guard changes are proposed. Preserve each rejecting row before validation and
preserve forensic export independently of live qualification. K/L recurrence of
runc initializers was a measurement side effect, fixed with persistent observer
lanes and startup-only exec probes, not by omitting PSS reads.

Ranked hypotheses for L: (1) THP allocation/compaction/direct reclaim, (2) hidden
ancestor limit, (3) other node activity. L has simultaneous direct reclaim and
large anon_thp growth; post-stop kernel is THP always/defrag madvise. Node cgroup
max/high are max; Docker memory/swap quota0, worker limit5GiB and events0 argue
against an observed local hard-limit cause. Ancestor and global fragmentation
state at the exact trigger were not captured. Other tasks remain possible.

The diagnostic command `run_probe.py` created one non-root 256MiB-capped,
120-second disposable Pod; each arm touched64MiB with NumPy, no inference.
Default used63,488KiB AnonHugePages and31THP allocations. Process-disabled used0,
with readback and exec-child inheritance1. Neither arm caused direct reclaim or
PSI. Thus it validates a controlled intervention, not a minimized PSI repro.
M is a single new runtime hypothesis test, with all original guards retained and
additional vmstat deltas. It cannot retrospectively prove why L failed.

Kernel semantics: https://docs.kernel.org/admin-guide/mm/transhuge.html .
