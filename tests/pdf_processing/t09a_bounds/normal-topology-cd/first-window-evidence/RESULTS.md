# CD: four complete results; final Wiki06 stopped by object PSI

CD ran once with the same producer, five-document sequence, 32 active historical
Deployments, temporary object 1Gi limit and unchanged guards as CC. All 11
pre-inference gates passed. Wiki06, YOLO07, AIMA08 and native51 each completed
required work and passed the local full-result checks. This is the fixture
oracle, not a universal canonical-quality claim (`canonical_accepted=false`).
The final Wiki06 parsed/registered 28 pages and completed 10/11 selected OCR
components before the stop; the complete sequence did not pass.

At 2026-09-27 05:23:24.404 UTC the targeted object cgroup first showed full PSI
+417 microseconds; the controller stopped at 05:23:24.413 UTC. It reached
420 microseconds through cleanup. At onset memory.current was 605,626,368 bytes
of 1Gi, swap.current=0, swap.max=0, and high/max/OOM counters zero. VM swap,
direct-reclaim and compaction counters did not increase across the immediate
200ms onset interval. Compaction had increased just before that interval, so
this does not rule out earlier pressure.

The object file-refault counter was 6,173 at onset and 6,371 about one second
later; memory.stat updates are batched and that later sample overlaps
cancellation. MinIO D-state stacks in the onset interval include
`folio_wait_bit_common -> filemap_get_pages -> filemap_read` and ext4 directory
reads. This supports a cache-refault/read-wait hypothesis, but the sched filter
captured all MinIO processes and did not retain each thread's cgroup: those
individual stacks cannot conclusively be assigned to the target object Pod.
A direct `psi_memstall_enter` caller trace is needed for that missing link.
No trace buffer overrun or dropped event was reported. The initial 100-stack
capture limit was removed during admission (recorded in trace-adjustment.json),
before the failing workload interval; workload and guards were unchanged.

Temporal confirms no ActivityTaskFailed before cancellation. The final workflow
execution COMPLETED after cancellation with business status failed /
activity_budget_exhausted, processing_complete=false, 28 registered pages and
10/11 components. The business error is downstream of guard cancellation.
The request-20 recycle occurred and later groups completed with parser PID1836;
full post-recycle document completion remains unqualified in this run.

Failure sealing and cleanup passed: stopped markers prove parser/scratch
absence; workload Pod absent; evidence PVC retained Bound; 32 exact Deployments
0/0 with no owned Pods; object restored to 512Mi/Ready; tracer exited and its
private instance removed. No automatic retry occurred.

| Gate | CD result |
|---|---|
| Admission, source/runtime contracts, 11 pre-inference gates | Pass |
| First four full fixture results | Local checks passed |
| Planned recycle and subsequent group processing | Observed |
| Final Wiki06 and complete mixed sequence | Incomplete |
| Object full PSI guard | Failed (+417us at onset) |
| OOM / object swap at onset | None / zero |
| Evidence sealing and restoration | Pass |
| #44 supported normal operating scope / closure | Not established |

Raw evidence is preserved in `/private/tmp/t09a-bounds-20260927-cd`,
`/private/tmp/t09a-bounds-object-20260927-cd`, and
`/private/tmp/t09a-normal-topology-20260927-cd`. The full trace is retained here
compressed, with onset, business reconciliation, and cleanup records.
Run `python3 tests/pdf_processing/t09a_bounds/normal-topology-cd/summarize.py`
against those raw directories to reproduce the summary assertions.
