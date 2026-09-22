# Q04 AC warm runtime result

AC ran once with identity `q04-warm-pod-cgroup-20260922-ac`; it was not retried. All 11 pre-inference gates passed. All five Temporal workflows completed with `processing_complete=true` and registered 28, 15, 12, 51, and 28 pages. The 29-group sequence reused parser PID 130 through request 20, recycled once to PID 1835, and completed the second 06 case.

The resource window passed its cgroup qualification: 1,401 samples, maximum gap 0.7014 s, node and Pod-cgroup full PSI `avg10=0.0`, no VM or cgroup OOM, minimum node available memory 5,241,487,360 bytes, outer maximum cgroup memory 2,520,711,168 bytes, and inner maximum 2,554,904,576 bytes. The cgroup peak sample had complete process attribution; AB's peak sample was also complete, so this single run does not prove that read ordering eliminated the earlier race.

The overall acceptance result is still **FAIL**. During controlled terminal cleanup, worker PID 111 (`start_ticks=20153996`) exited while sample 1399 read its process files. Adjacent samples and the exact exit event prove cgroup continuity, so `cgroup_resource_complete=true`; the missing worker PSS remains unknown, so `process_attribution_complete=false`. This was a terminal measurement race after all business work and peak observation, not PSI, OOM, memory floor, deadline, Activity failure, supervisor interruption, or ingestion failure.

The runner returned 1, did not retry, sealed the workload evidence, deleted the owned Deployment, Pod, and ConfigMaps with identity checks, retained PVC `q04-pod-cgroup-ac-evidence-20260922-ac` (UID `3599cdcb-dfb1-41fc-8aec-1bac4df0584b`, Bound), and independently verified all 32 held Deployments remained at zero replicas.

The next repair must coordinate the terminal worker transition with the sampler while preserving continuous independent cgroup observation and the rule that unknown PSS is never accepted as complete. AC is evidence for successful ingestion, parser recycle, peak attribution, and resource capacity; it is not a Q04 pass and does not make #51 closable.
