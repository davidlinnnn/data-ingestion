# DE: bounded generic MinIO PUT/GET did not reproduce DD PSI

One diagnostic execution at `ae83bb9`, identity `object-rw-de`, used the DD
candidate rollout (request768Mi/limit1Gi/Recreate), all32 historical Deployments
Ready, and the original zero-new-object-full-PSI/max/OOM and VM guards. It ran
no ingestion and had no automatic retry. Four fresh8MiB objects were each PUT
once with conditional create and GET once, then retained under
`t09a/object-probe-20260928-de/`. The32MiB write/read bound and exact responses
were checked locally before runtime.

Result: **PASS_NEGATIVE_CONTROL**. PUT latency was31.9–34.3ms; GET latency was
8.4–13.4ms. Across58 saved samples the exact MinIO container/Pod stayed at1GiB,
object full PSI delta was0, and local low/high/max/OOM counters did not change.
Maximum object charge was162,869,248bytes and minimum VM available was
5,582,422,016bytes. VM direct/background scans, compaction, allocstall and OOM
did not increase; file refaults increased9,107.

The direct tracer recorded11 `folio_wait_bit_common` and6 `read_pages` memory
stall entries elsewhere in the VM, none in the exact MinIO container. Trace
buffers report zero overrun/drop. Because the target had no PSI event, DE has
no target stall callsite to report. This is a valid negative control, not proof
that DD's intermittent event is resolved.

DE is materially smaller than DD: a fresh MinIO Pod ended near155MiB and only
four large keys were created. DD reached about478MiB at its first trigger after
464 retained objects (124 below4KiB,323 from4KiB to1MiB,17 at least1MiB) and
three complete workflows plus part of native. Generic large-object PUT/GET and
the32-on topology are therefore insufficient on their own. The leading next
hypotheses are the real Store publish pattern's many small keys/metadata paths,
accumulated cache/reclaim state, and intermittent MinIO directory scanning.

Cleanup independently passed: exact128Mi/512Mi/RollingUpdate restored,32 exact
Deployments off with no owned Pods, Temporal idle, objectHTTP200, original PVC
UID/PV Bound, and the trace container/private instance absent. The four DE
objects remain retained; nothing was deleted. `verify_de.py` replays all formal
guards, operation ordering/latencies and trace loss/attribution checks.

This result does not qualify the permanent candidate or close #44. It rules out
another identical large-object probe. A next diagnostic, if run, should replay
the retained DD object's many-small-file publish/readback shape under a fresh
prefix and the same direct trace, still bounded and without PDF inference.
