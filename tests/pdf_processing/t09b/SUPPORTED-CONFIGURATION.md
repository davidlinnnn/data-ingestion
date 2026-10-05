# T09b / #45 selected configuration and bounded acceptance

2026-09-30. Selected group5, one active parser child. No production setting,
resource limit, quality expectation or #44/#51 scope is widened. This report
consolidates the completed comparison; integration review targets dev, never main.

## Selection and comparison

Three matched normal pairs (A6/B2, B4/A7, A11/B5) passed the fixed mixed sequence,
complete graph/checks equality, required OCR, runtime guards and cleanup. Group10
controller median517.67s versus group5 526.83s (1.7% difference); ranges overlap.
Median whole-Pod peaks were3,213,393,920 versus2,830,946,304B, and server HTTP TX
4,095,841,710 versus3,614,672,367B. Small timing differences do not justify more
memory, traffic and repeated recovery work. Retain group5.

RA2/RB1 retained the same10 durable native pages. Group5 repeated5 pages and
group10 repeated10. Loss-to-business completion bounds were112.7156–112.7365s
versus116.5663–116.5868s; server TX1,614,996,847 versus1,867,302,641B.
This is one matched fault pair, not a recovery distribution or SLA.
See RECOVERY-COMPARISON.md for attribution, inventories and limitations.

Process-cold and later-request observations have n=3 per fixture in
COLD-WARM-DISTRIBUTIONS.md. Fresh-process timing includes required OCR; host and
storage caches are uncontrolled. Native later-request work crosses request20
recycle and is not wholly warm. Timings exclude external verifier and worker
startup; stage sums and nested publication/readback timers are not additive.
No p95, confidence, backend ranking or production-capacity claim follows.

## Buffering measurement boundary

Publication instrumentation counts unique serialized bytes objects held in the
input files dictionary for the entire Store.publish call, including its upload,
registration and integrity readback. Aliased references count once; concurrent
publication inputs are deduplicated by object identity. GET instrumentation
separately records the largest returned read chunk. A12 measured:

| Fixture | Peak publication input bytes | Largest GET chunk bytes | Application read amplification |
| --- | ---: | ---: | ---: |
| Wiki06 |22,934,707|8,860,065|12.2386|
| YOLO07 |14,460,723|4,875,372|9.4090|
| AIMA08 |28,896,640|20,876,815|6.1748|
| native51 |70,573,839|22,539,322|10.5860|

Source: a12-evidence/storage-cost.json; complete retained worker ledgers.
Read amplification is successful application GET bytes divided by distinct
object-key payload bytes required by the request, not HTTP wire amplification.
Actual server request bytes are separately reconciled; failed/unknown attempts
are never counted as zero. Recovery includes all worker generations.

These are scoped payload-buffer peaks, not a total simultaneous buffer peak.
The two columns cannot be added: independent peaks need not coincide. Caller
retention after GET return, decoded objects, parser/native and SDK transport
allocations are not individually measured; their isolated byte counts remain
unknown. Whole-Pod memory covers their aggregate safety impact, including cache
and kernel charges, but is not relabelled as buffering. This satisfies the
scoped application-buffer/readback comparison; no exhaustive allocation-profiler
or aggregate serialized-I/O-peak claim is made. Earlier pending statements about
full retained/native profiling are superseded only by this explicit scope.

## Conditional concurrency admission decision

C was evaluated for admission and is not admitted under the retained budget.
No two-child runtime was launched or failed. CONCURRENCY-ADMISSION.json binds each
input to its raw sample, process identity and metric:

| Planning reservation input | Bytes | Evidence |
| --- | ---: | --- |
| One parser resident anonymous memory |1,968,775,168|A7 RSSAnon high|
| One worker |273,934,336|A12 PSS high|
| Controller |318,318,592|A6 PSS high|
| Two parsers + shared worker + controller |4,529,803,264|Reservation scenario|
| Existing worker sample guard |4,294,967,296|4GiB, unchanged|

The reservation exceeds the guard by234,835,968B before any additional kernel,
file-cache or concurrent buffering allowance. Two isolated workers would reserve
4,803,737,600B. These independent single-child observations are planning inputs,
not simultaneous peaks, proven upper/lower bounds or physical-impossibility proof.
RSSAnon excludes file mappings; PSS apportions shared mappings. No guaranteed
anonymous-sharing credit is assumed for an unreviewed isolated parser pool.

A12 minimum VM available2,606,751,744B minus an assumed extra parser and worker
reservation2,242,709,504B leaves364,042,240B, below the unchanged1.5GiB floor.
This is a planning scenario, not a prediction of reclaimability or MemAvailable.
Current evidence cannot establish a reviewed two-child budget within these
assumptions. PLAN explicitly permits nonadmission and serial support. Therefore
select one child, one active parser slot, serialized business work; two-child
throughput, profile isolation and concurrent recovery remain unqualified.
Reconsider only with a reviewed implementation and budget inside existing limits
or a separately approved resource/scope change. Increasing Temporal concurrency
on the current shared mutable converter is not a supported implementation.

## Tested workload versus configured admission ceilings

| Qualified comparison fixture | Input bytes | Pages | Required component OCR | Mapping |
| --- | ---: | ---: | ---: | --- |
| WikiSkill06 |1,177,706|28|11|Original PDF1–28|
| YOLO07 |919,273|15|4|Original PDF1–15|
| AIMA08 selected chapter pages |308,913|12|9|Original PDF99–110; retained book mapping|
| native51 |1,817,841|51|7|Original PDF1–51|

Source/profile/model identities and source page mappings remain in per-cell
manifests/configs and the accepted input bundle; no additional payload rehash.
All selected runs preserve full document/checks equivalence and reviewed evidence.
Quality is evidence-specific: bounded reviewed regions do not establish universal
reading-order, relationship, table, language or formula correctness. Existing
representation losses and unknown relationships remain visible. Formula source
evidence is preserved; formula interpretation/enrichment is excluded.
No scan-first/unreliable-native repair, arbitrary books, whole1151-page AIMA,
PPT-wide support or automatic OCR-strategy detection is qualified by this ticket.

SUPPORTED-BOUNDS.json exports the actual A12 selected configuration. Revalidation
consists of unchanged projected contract/pre-inference gates, complete selected
normal/recovery/cold results and local launch/lifecycle regressions; no tuning
change invalidates #44 bounds. Configured ceilings do not qualify every file
below them or prove edge-of-ceiling runtime capacity.

| Processing configuration | Retained value |
| --- | --- |
| PDF file/page/per-page pixel ceilings |100MiB /51 pages /20,000,000 pixels|
| Fresh preflight / child request deadline |30s /540s|
| Parser startup / no-progress |120s /180s|
| Terminate / reap / drain |5s /5s /30s|
| Warm recycle |20 requests; one active slot per child|
| Worker resources |4CPU;5GiB hard limit;4GiB sample guard|
| OCR intra-op / huge-page launch policy |4 /NUMPY_MADVISE_HUGEPAGE=0|
| Object service |768Mi request /1Gi limit /Recreate; memory.low unmanaged|
| Temporal Activity start/schedule-to-close |12min /40min|
| Activity heartbeat / retry |15s;3 attempts,2s initial/10s maximum interval|

Temporal finite Activity retries are distinct from the harness: each controlled
runtime has a fresh identity/prefix, stops on failure, and has no automatic run
retry. Processing budgets are not an admission/outage guarantee or deadline SLA.

| Controlled acceptance/admission setting | Retained value |
| --- | --- |
| Outer observation / continuous admission |180s /60s|
| Outer available-memory admission |4.5GiB|
| Case admission observation / available memory |60s /3GiB|
| Runtime VM available floor |1.5GiB|
| Authorized window / minimum work / cleanup reserve |1500s /825s /300s|
| Replacement bound |120s|
| Cgroup cadence / maximum sample gap |250ms /1s|
| Transport cadence |2s|
| OOM |Fatal; zero accepted VM/worker/object OOM|
| Worker full PSI avg10 |Zero; fatal if positive|
| Node PSI |Approved A4 runtime telemetry policy; admission retained|
| Object PSI / max events |Sustained full avg10 positive fatal; cumulative full and max-event deltas recorded under approved policy|

Terminal VM PSI is telemetry only after durable workload completion and worker
stop proof; OOM/floor guards remain active. These approved diagnostic policies do
not imply absence of stalls. PC3 object max-event delta13 and cumulative full PSI
10,586us remain recorded. Normal topology used32 historical Deployments active
during explicitly declared windows, restored off afterward; no wider workload
or production environment is qualified.

## Cleanup, unresolved causes and integration

PC1 readiness wait held the sampling transition lock for1.009470s, causing a
1.021253s sample gap. The root-cause fix narrows the lock to launch; regression
uses the real transition method. PC1 evidence remains excluded; PC1B replaces it
with a new identity. A9/A10 MinIO reader ValueError's intermittent trigger remains
unknown; subsequent successes do not prove that original cause. Failed cells
and all historical Q04 evidence remain intact.

Successful cells restored all32 held Deployments off, proved no owned Pods or
restoration errors and preserved object identity/config. Evidence PVCs and object
prefixes remain retained. Main checkout is unchanged. No additional runtime is
needed to select group5/one child under this bounded scope. This report supports
final dev integration review; two-child and excluded allocation details remain
explicitly unqualified rather than being described as passed experiments.
