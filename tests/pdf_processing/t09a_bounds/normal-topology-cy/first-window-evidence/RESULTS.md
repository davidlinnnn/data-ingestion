# CY: OCR allocator pressure reproduced and process identity established

11 pre-inference gates and125s protection admission passed under32-on normal
load. FirstWiki06 native grouped capture registered28pages. The first component
OCR ran once, produced report/crop, then the diagnostic stopped it deliberately
with a non-retryable configuration code. No second component or later fixture ran.
This is neither ingestion success nor a full-window acceptance result.

## What is now proven

Host TGID1074490 maps through NStgid to container PID219; process start_ticks
43414297 matches the OCR phase record. During inference,230 psi_memstall_enter
entries came from exactly this OCR process: its main thread plus17 threads created
between engine_start and engine_ready (container TIDs226–242). All230 entries lie
inside the measured inference interval.99 parsed stacks include
vma_alloc_zeroed_movable_folio. The enclosing VM sample interval records
allocstall_movable+231,pgscan_direct+38353,pgscan_kswapd+47720,compact_stall+0,
and full PSI total+39026us. Calls are entry counts, not duration shares.

Together with CT2's actual ONNX session-constructor observations, this supports
parallel OCR native-pool allocations as a concrete contributor to shared-VM
reclaim pressure. It does not prove exclusive responsibility for all global PSI,
identify the specific ONNX model from CY alone, or prove that4threads removes it.
One early trace call is unidentifiable; the matched OCR calls are fully identified.
Trace end reports zero buffer loss. Object full PSI delta was0 in this run.

## Ordering (UTC2026-09-27)

-17:06:24.711701: OCR inference starts,58threads total.
-17:06:24.814753–17:06:25.717815:230 precisely attributed allocator entries.
-17:06:26.107613: OCR inference returns.
-17:06:26.136375: output retained and deliberate diagnostic stop marker written.
-17:06:26.206705: component Activity fails non-retryably,attempt1.
-17:06:26.215950: workflow COMPLETED with businessfailed,
  cy_diagnostic_first_component_complete,processing_complete=false,0components.
-17:06:26.931202: sampled VM full avg10 updates to0.18; outer guard records stop
  at17:06:26.932342. No workflow cancellation was needed: it was already terminal.

Thus CY's business failure is intentional and precedes the delayed average guard;
it did not cause the earlier allocator/reclaim wave. Preserve CS's distinct
cancellation ordering; do not copy that ordering onto this diagnostic.

## Next controlled contrast

The default now reproduces the target allocator path under normal load with exact
OCR identity. One fresh diagnostic may therefore change only the supported ONNX
intra-op parameter to4, retain the first-component boundary and all resource
policies, and compare the complete OCR report/crop to CY. Keep the runtime override
explicit and diagnostic-only; do not promote production changes from the prior
32-off timing result. No unchanged retry or full-matrix run is justified.

## Restoration

Independent cleanup PASS:32off/no owned Pods; object512Mi Ready/HTTP200; all
manager/kernel low values restored; worker,object observer,diagnostic containers
and private trace instances absent. CY PVC remains Bound and prefix is retained.
#44 remains open and #45 blocked; historical #51/Q04 is unaffected.
