# CP: exact object workingset-read stalls caused the guard stop

CP ran once with the real [06,07,08,native,06] workload, all32 historical
Deployments active, temporary object1Gi, the previously fixed OCR-only NumPy
policy, and unchanged formal resource/deadline guards. All11 pre-inference gates
passed. The new250ms object observer recorded six levels of ancestor state.
No production fix or automatic retry was introduced.

## Cause and ordering

At2026-09-27 07:21:21.371437 UTC the exact object container entered memory PSI
from `read_pages`; the following direct stacks also enter from
`folio_wait_bit_common`. All14 pre-stop calls (8read_pages,6folio_wait_bit_common)
belong to MinIO TGID860747 in Pod7eb766f6-ae8d-43d3-9c5f-e1f676df33f3 /
containerf9c6b60e1c143d2f4c5eb8ddb819b65a6a39e9dca35904b3efaa7e72a38beb49.
They traverse `ext4_file_read_iter -> filemap_read -> filemap_get_pages`;
there is no pre-stop `try_charge_memcg` caller.

- 07:21:21.237211: preceding object sample, PSI0.
- 07:21:21.371437–.373052:14 attributed read/readahead-wait PSI entries.
- 07:21:21.489096: first retained object full-PSI sample155us.
- 07:21:21.627321: controller records object-service max/full-PSI stop.
- 07:21:21.980065: Temporal cancellation requested.
- 07:21:21.997516: native workflow COMPLETED with business failure.

At onset object usage494,993,408 bytes (~472MiB) and Pod usage495,280,128 bytes
were below their1Gi limits. All six observed levels had high/max/OOM counters0;
object swap0. VM available at the stop was3,467,022,336 bytes and full avg10=0.
The immediate252ms onset interval had no new VM scan/compaction/OOM events;
object file refaults increased445. Earlier in the run VM scans had increased
7,967direct/400,230background and object scans768direct/18,715background.
Counter updates are batched: do not interpret the interval as proof that no
previous reclaim caused these reads, or identify a specific eviction victim.

Linux v6.12's [read_pages implementation](https://raw.githubusercontent.com/torvalds/linux/v6.12/mm/readahead.c)
marks readahead as a memory stall when the pages are recognized as workingset.
The captured path therefore identifies workingset page reads/waits, rather than
a demonstrated hard-limit charge stall. This is real PSI, not a fabricated
sample or proof of OOM. It differs from CK's512MiB `try_charge_memcg` mechanism.
The exact object key, earlier evicting allocation, and a universally sufficient
resource setting remain unknown. CP supports CD's earlier read/refault hypothesis;
it cannot retroactively supply CD's missing task attribution.

## Functional result and resource observations

| Gate | CP result |
| --- | --- |
| Runtime/source/import contract and11 pre-inference gates | Passed |
| Wiki06,YOLO07,AIMA08 | Complete; full document and checks JSON equal accepted AI/AJ fresh references |
| Native51 | Failed after15 registered pages; processing_complete=false |
| Final Wiki06 | Not started |
| Full29-request/recycle/post-recycle sequence | Not established by CP |
| Object full PSI | First155us;431us through cleanup; failed original guard |
| OOM or ancestor hard-limit/high events | None observed |
| Failure sealing / environment restoration | Passed |

There were no ActivityTaskFailed events before cancellation. Native's
`activity_budget_exhausted` result follows the guard cancellation; it is not
an independently demonstrated activity-budget timeout. The three completed
fixtures retain canonical_accepted=false under the already-reviewed bounded
contract; their complete graph equality does not imply universal quality.

Object telemetry:1,601samples,max gap0.260887s,max usage502,816,768 bytes.
Worker max2,484,260,864 bytes; minimum measured VM available3,010,260,992 bytes.
Direct tracing retained32 target entries total,14before stop and18after it;
all identities resolved and trace buffers report zero overrun/dropped events.
Do not use cleanup-period entries to claim the stop's cause.

## Validation and cleanup

Preparation commit:f0d7578. Independent Standards/Spec reviews found0/0 issues.
The new sampler regression preserves parent-only events. CP's real activation
loop was replayed against an applied-patch/response-timeout; actual subprocess
handoff tests passed. The runtime image imported the projected CP adapters and
validated the exact sequence/recycle contract before execution.

`python3 -B tests/pdf_processing/t09a_bounds/normal-topology-cp/verify_failure.py`
passes against retained evidence: exact pre-stop task stacks, ancestor limits,
actual runner guard rejection and stop-before-Temporal-cancel ordering.
The stack parser also recovered all three known CK charge stacks as a positive
control. Complete JSON/check comparison passed for the first three fixtures.

Controller and independent cleanup both passed:32Deployments0/0/no owned Pods,
object512Mi/Ready/health200, worker and object observer absent, diagnostic
containers/private trace instances absent. Evidence PVC is Bound; historical
PVCs/prefixes were preserved. The supervisor recorded parser/scratch absence.
Raw evidence remains under `/private/tmp/t09a-bounds-20260927-cp`,
`/private/tmp/t09a-bounds-object-20260927-cp` and
`/private/tmp/t09a-normal-topology-20260927-cp`.

## Next candidate, not yet applied

Do not rerun unchanged or raise memory.max simply because PSI appeared below it.
The existing object path has memory.low/min=0 at every inspected level through
the host Docker ancestor (`restored-memory-protection.json`). A bounded candidate
is best-effort memory.low protection for the object working set, with effective
protection propagated along the exact ancestor path, preserving object memory.max1Gi,
worker settings and every existing guard. Start with768MiB protection as a trial
ceiling covering CG's observed734,961,664-byte object peak; this is not a proven
minimum or permanent setting. Protection is one shared hierarchical allowance,
not768MiB of additional allocation at every level.

The [kernel contract](https://www.kernel.org/doc/html/v6.12/admin-guide/cgroup-v2.html)
makes memory.low best effort and ancestor-limited; it is not hard memory.min,
and it may transfer reclaim pressure to other workloads. Before any runtime,
verify effective ancestor allocation and exact restoration locally, snapshot all
changed low values, keep the same VM floor/OOM/PSI guards, then evaluate one new
identity with the actual workload. Restore all protection values and32-off/
object512Mi afterward. Reject the candidate on pressure or changed output; do not
turn this proposal into a permanent default based on theory.

#44 remains open and#45 blocked;#51 remains historically closed. This run resolves
the classification of this stop but does not satisfy the full resource envelope.
Issue update is a local draft for unified publication.
