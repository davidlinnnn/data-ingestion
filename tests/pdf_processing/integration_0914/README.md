# T08 + partial T09a integration — 2026-09-14

Integration regression: **PASS**. T08's declared phased rollout remains PASS;
T09a remains **PARTIAL / OPEN**. This does not qualify warm resource bounds,
planned recycling, long-workload drain/recovery, or unresolved AIMA source quality.

Integrated parents:

- T08 `747bbdf7c50d726d574c3283e8a47ac5fc70a139`.
- T09a `863d2d1b17ff953e23924268408fc288b90e8772`.

The README conflict preserved both routing and zero-width combining-mark contracts.
No production code was changed beyond merging these parents. Two T08 inspection
tools now assert that Temporal returned a status before reading its name; the
broader integration typecheck identified these optional-value accesses.

## Executed checks

- [Full suite](evidence/full-suite.log): 10 tests passed in 33.052 seconds, including
  fresh-process scanned restoration. Executed with the retained macOS prototype
  Python/model/fixture paths and the shared qualification lock.
- [Typecheck](evidence/typecheck.log): zero errors/warnings for the integrated
  package, deployment entrypoint, T08 and T09a tools. An initial incorrectly absolute
  include list was ignored by Pyright; that broad scan was stopped and excluded.
  The final configuration uses explicit relative includes.
- [Real Temporal/K8s result](evidence/result.json): new producer, new request ID,
  content-addressed stage queues and `t08/integration-0914/` object prefix. A fresh
  one-page/two-picture source completed seven actual routed Activities, both
  required OCR outcomes and durable content evidence before processing complete.
  Canonical acceptance remains false. Missing/malformed routing and a mismatched
  worker queue were rejected. [Runtime log](evidence/runtime.log).
- [Geometry writer](evidence/geometry.log): the actual evidence writer preserved
  a synthetic U+0338 zero-width TextItem, original provenance, full-page crop recipe
  and explicit uncertainty. Ordinary/reversed/outside/zero-height geometry and a
  false reviewed-formula overlap were rejected. The Linux coordinator ran this
  bounded rendering check without parsing/OCR inference. The initial local attempt
  failed to import the Linux Temporal native library and is not a passing test.
- Both original evidence seals verified against their respective parent commits:
  T08 61 files, T09a 82 files. Their source attribution is historical: T09a's sealed
  `processing_workflow.py` and deployment worker differ in the combined tree due
  to T08. Verify historical seals against the named commit, not by rewriting them
  to match integrated source.
- `git diff --check` passed. The runtime Pod recorded zero restarts and was normally
  deleted; [cleanup](evidence/cleanup.json) records absence before lock release.

The bounded runtime used one Pod hosting all stage pollers and fresh parser children
with the retained pinned ARM64 image. It checks the combined interface seam, not
the separately deployed rollout matrix, memory bounds, worker drain or HA. No old
T09a workflow was resumed. The source and output bytes stay private in object storage.

## Reproduction and handoff

`runtime.py` contains the assertions; `controller.py` records the host controller
used for this run. It requires the retained T08 coordinator Pod-spec snapshot at
`/private/tmp/pdf-integration-coordinator.json`, fixture ConfigMap, Temporal/MinIO
services, image/model bytes and the checkout path recorded in the controller.
Immutable ConfigMaps must not be overwritten for changed source: choose fresh
names, queues and request IDs for another producer. This is an experiment driver,
not production deployment tooling. `geometry.py` is a small standalone regression
for a compatible runtime with the integrated package on `PYTHONPATH`.

Keep #44 open. Resume its resource diagnosis before another long qualification
window; preserve remaining warm/recycle, drain/replay, harness and source-quality
gates. #45 remains blocked by #44, and #46 still waits for #45 after #43 closes.
Old accepted requests require their original producer/configuration; do not poll
their queues with this combined producer. The new evidence interface requires
consumers to use the declared crop recipe and geometry status rather than infer
crop extent from a zero-width box.
