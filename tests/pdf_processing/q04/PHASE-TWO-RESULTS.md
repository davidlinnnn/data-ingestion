# Phase-two local handoff (#51)

Implemented the six-fixture runtime adapter on the phase-one branch. **No new
Temporal workflow, PDF native inference trial, service pause, Pod deletion or
replica mutation was executed.** Read-only copies of five retained R3 document and
content-evidence JSON files were taken from the coordinator to new private local
directories for complete-graph regression. Original bytes remain unchanged.

## Local evidence

- Combined local PDF + Q04 suite: **93 tests PASS**, 61.315 seconds;
  `evidence/adapter-full-suite.log`. Includes 74 existing PDF regressions and 19
  Q04 checks, real local source rendering and owned sleeping-process cleanup.
- New harness typecheck: **0 errors/warnings**. CLI help works without services;
  missing capacity acknowledgement is rejected before any source/service access.
- Private bundle integrity: all six original/captured PDFs, six full graph
  expectations, six source-oracle files and harness/producer hashes verified.
- All five retained R3 graphs pass complete consumer graph and independent
  per-fixture checks. Corrected AIMA passes exact graph, all four algorithm oracles
  and all eight accepted continuation conditions. Corrupt graph/cell/caption/
  reference/PNG/checkpoint, missing/reused OCR, vacuous reuse, wrong retry, early
  warm PID changes, telemetry gaps/OOM and later-page forbidden publication are
  rejected by local tests.
- Controller replay test uses a fake external Workflow transport with the actual
  checked Store and consumer; it does not claim real Temporal replay. Cleanup test
  terminates only a real owned sleeping process tree and preserves an unrelated
  sleeping process. These are local harness proofs, not resource/drain qualification.

The initial RED import, platform/process-inspection restriction, source-coordinate
conversion mistake, and intermediate typecheck failures are retained as separate
logs. AIMA anchors were corrected to compare TOPLEFT checkpoint geometry with
BOTTOMLEFT document geometry using the recorded page height; no source text,
fixture, accepted edge or production code changed. The q04 driver uses the unique
module name `q04_runtime` to avoid historical `runtime.py` test-import collisions.

`evidence/phase-two-local.json` binds the final harness, producer, private input
bundle and retained graph/oracle hashes. Earlier bundle snapshots are preparation
history; verify or regenerate a new bundle whenever harness bytes change.

## Main-session decision before execution

Review [RUNTIME-ADAPTER.md](RUNTIME-ADAPTER.md), choose process or explicitly owned
Pod scope and confirm its topology prerequisites. Approve a current capacity file
with thresholds, deadline and cleanup reserve. Start with the one-page Keynote
sentinel, then schedule six-fixture matrix subsets, the fixed warm sequence, drain
and telemetry-loss guard as separate bounded windows where needed. Matrix input
and output artifacts remain immutable across windows.

A native method-change case removes the opt-in continuation selection under a new
immutable release; it exercises actual invalidation while the original accepted
request remains pinned to its original profile. Any extra graph changes outside
the reviewed AIMA expectations fail with a retained delta, requiring main source
review before acceptance. They cannot silently be accepted by fresh/restored
matching. #44 remains final acceptance, #45 calibration and #46 packaging.
