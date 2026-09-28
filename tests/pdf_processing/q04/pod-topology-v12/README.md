# M — bounded test of the THP pressure hypothesis

L fixed recurring-exec measurement interference: all 290 process samples were
complete. Its fresh attempt still stopped on real node full PSI 0.36, with cgroup
direct reclaim and increasing pressure totals, no OOM, and 6.04 GiB MemAvailable.
This is not evidence that the pressure guard was wrong.

M applies PR_SET_THP_DISABLE only to the workload supervisor, verifies readback,
records the policy before launching descendants, and inherits it through
fork/exec. No global kernel setting, producer, semantic oracle, parser recycle
policy, memory limit, PSI/OOM/floor/deadline or attribution criterion changes.
The controller additionally records allocation/compaction vmstat counters.

The capped no-inference 64 MiB probe showed 62 MiB AnonHugePages by default and
zero with the inherited process policy. Neither arm reproduced pressure: this
supports the mechanism, not a proven diagnosis of L. One new M window tests
whether the actual workload can qualify under this explicit runtime policy.
Any failure stops; no retry. A pass qualifies only M and does not reclassify L.

Linux documents direct reclaim/compaction for advised THP regions under madvise
defrag, and the inherited per-process disable switch:
https://docs.kernel.org/admin-guide/mm/transhuge.html .
