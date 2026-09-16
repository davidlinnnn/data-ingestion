# Phase-one results and main-session handoff

No new runtime window has been used. Q04/#51 remains open and #44 is not accepted.
Production and deployment files are unchanged from `6d929e1`.

## Static evidence

- `evidence/static-audit-v2.json`: 20 production hashes match Q03 A/D; corrected
  trial-D driver hash matches; four full-case records and 22 matrix cases verified.
- All 61 R3 sealed files match. All 499 private trial-D artifact hashes and 20
  retained trial-A full-case metadata/history hashes match. This is an integrity
  reconciliation, not a new runtime trial or an independent content review.
- Six source PDF hashes match; source page scopes are native 51, WikiSkill 28,
  YOLO 15, AIMA 99–110, ACL 2–4 and Keynote one page. Supplementary page mappings
  match the retained R3 profile by numeric physical page, not JSON key order.
- Real dependency projections confirm conservative all-stage R3 invalidation and
  evidence-only parse/assembly compatibility. `audit-negative-checks.log` proves
  corrupt input fails before a report and existing output cannot be overwritten.
- `static-audit.json` is the earlier preparation snapshot before the full-case
  private-file/page-map checks were added; its harness hash names that earlier
  script. Use v2 for current reproduction. No historical snapshot is rewritten.

## Local validation and retained failures

Focused Q03 compatibility: 3 PASS (`compatibility.log`). New preparation harness
Pyright: 0 errors/warnings (`typecheck-final.log`). Full local PDF suite: 74 PASS in 50.979 seconds (`full-suite.log`).

First focused invocation used Linux-only `t01-type-deps` on macOS and failed
importing the Temporal bridge. `compatibility-wrong-platform.log` is retained;
using the already available macOS `q02-deps` fixed the environment without installs.
First full-suite invocation lacked private fixture/model roots in the independent
worktree: 73 passed and scanned restoration failed. It remains in
`full-suite-missing-fixtures.log`. The rerun uses the existing
`PDF_TEST_FIXTURE_ROOT` override and holds the shared local qualification lock.
An initial new page-map check exposed lexicographically sorted JSON keys; comparison
now uses numeric physical pages. No fixture, extraction, production or historical
runtime evidence was changed to make a check pass.

## Remaining work

Main reviews this preparation commit, its stage-impact/reuse decisions and fixed
fixture inventory. Adapt the cross-fixture runtime driver and oracle paths as
specified in ACCEPTANCE-PLAN before seeking a new capacity window. Then qualify
pending six-fixture fresh/restored/replay and affected warm/resource/drain behavior,
review every new merge delta, and hand measured limits to #44. Reuse Q03's unchanged
bounded AIMA delivery/barrier proof only with the stated identity checks.

No service pause, workload submission, replica change, deletion, GitHub message,
push, merge or ticket closure occurred in this phase.
