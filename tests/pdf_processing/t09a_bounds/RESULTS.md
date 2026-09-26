# T09a bounded mixed-warm trial (2026-09-26)

The BK window passed its fixed mixed-warm scope on the existing
`kind-internal-a2a-vs6-local` cluster. It is one bounded run with the historical
Deployments held off and a temporary 1 GiB MinIO limit; it does not qualify the
normal all-Deployments-on operating envelope or establish a permanent MinIO
limit. Issue #44 remains open.

| Window | Identity | Result |
| --- | --- | --- |
| BI | `t09a-bounds-20260926-bi` | Stopped before inference: inherited supervisor rejected the valid `t09a-` run ID. No capacity conclusion. |
| BJ | `t09a-bounds-20260926-bj` | Stopped after workload start: inherited evidence mirror rejected the new phase path. Workload outcome unknown. |
| BK | `t09a-bounds-20260926-bk` | Passed the five-case mixed-warm sequence, Pod measurement contract, durable evidence export, and cleanup. |

BK evidence: `/private/tmp/t09a-bounds-20260926-bk` and retained PVC
`t09a-bounds-bk-evidence-20260926`. The sequence was Wiki 06, YOLO 07,
AIMA 08, native, Wiki 06: 29 group requests, one recycle at request 20,
two parser generations. The Pod measurement contract reports workload success,
complete qualification and 1,482 continuous 250 ms cgroup samples with zero
memory, OOM, and full-PSI violations. The durable terminal manifest is
`PASS_CANDIDATE`; workload exit was 0, with no timeout or forced stop. The
outer VM guard observed at least 4,651,737,088 available bytes and a maximum
2,526,662,656-byte worker cgroup reading.

The object observer recorded 2,228 samples under the temporary 1 GiB limit,
maximum memory.current 739,414,016 bytes, zero `memory.events.max` increase,
and zero full-PSI increase. The outer cleanup deleted BK-owned Deployment and
ConfigMaps with UID preconditions, retained the BK evidence PVC, and exported
the controller evidence. MinIO was restored to 512Mi and Ready 1/1; the BK
Deployment is absent. BI and BJ evidence PVCs and object prefixes were retained.

The phase record was written with fresh-output equality pending. A post-run
comparison against the accepted current-v3 fresh results completed that check:
BK's full `document.json` SHA and `full_reference_graph_sha256` match AI's fresh
Wiki06 and native outputs and AJ's fresh YOLO07 and AIMA08 outputs. Both BK
Wiki06 runs also match each other. All five BK accepted records are verified
and processing-complete, and retain the reviewed v3 continuation identity.
This comparison reuses the already accepted AI/AJ fresh runs; BK did not repeat
fresh-mode executions.

#44 still needs an agreed sustainable object-service setting and qualification
with the normal Deployment set restored. Do not infer those from one 1 GiB
isolated window.
