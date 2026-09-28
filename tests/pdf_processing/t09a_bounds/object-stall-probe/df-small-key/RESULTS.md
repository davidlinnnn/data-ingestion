# DF: bounded DD small-key replay did not reproduce object PSI

One execution at `1d45a82`, identity `object-small-key-df`, used the DD
candidate rollout (request768Mi/limit1Gi/Recreate), all32 historical Deployments
Ready, and the unchanged object/Pod PSI, max, OOM, VM floor and deadline guards.
It ran no ingestion and had no automatic retry. It copied the256 smallest
retained DD objects, preserving their key suffixes under the fresh
`t09a/object-probe-20260928-df/` prefix. Each object used source GET,
conditional destination PUT and exact destination GET readback in16-object
batches. The2,737,516-byte selection was fixed and checked locally before the
runtime.

Result: **PASS_NEGATIVE_CONTROL**. All256 objects completed in16 batches.
Median source GET, PUT and destination GET latency was0.77ms,1.71ms and0.74ms;
their maxima were6.91ms,7.38ms and1.14ms. Across79 saved samples the exact
object container/Pod stayed at1GiB, object full PSI delta was0, and local
low/high/max/OOM counters did not change. Maximum object charge was204,230,656
bytes and minimum VM available was5,466,816,512bytes. VM direct/background
scans, allocstall and OOM did not increase; compaction increased2 and file
refaults increased10,355.

Within the guarded window the direct tracer recorded10
`folio_wait_bit_common` and2 `__alloc_pages_direct_compact` memory-stall entries
elsewhere in the VM, none in the exact object container. Trace buffers report
zero overrun/drop. Therefore DF has no target MinIO callsite to attribute.

DF rules out this bounded many-small-key copy/readback shape, together with the
32-on topology, as a sufficient trigger. It does not reproduce DD's chronology,
three preceding producer workflows, repeated registry resolution, or the
candidate's roughly478MiB charge at first trigger. Accumulated producer/cache
state and intermittent background filesystem work remain plausible; their
relative contribution is unknown. Another standalone object-only probe would
not discriminate them.

Cleanup independently passed: exact128Mi/512Mi/RollingUpdate restored,32 exact
Deployments off with no owned Pods, Temporal idle, objectHTTP200, original PVC
UID/PV Bound, and the trace container/private instance absent. The256 DF
objects remain retained; nothing was deleted. `verify_df.py` replays all formal
guards, object count/bytes/latencies, trace loss and target attribution checks.

This negative control does not qualify the permanent candidate or close #44.
The next useful runtime must capture the exact object caller during a bounded
mixed producer window; it should only run with a concrete policy candidate,
because repeating DD unchanged would merely retest an already rejected window.
