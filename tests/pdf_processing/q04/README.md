# Q04 preparation and runtime-adapter handoff (#51)

Base: `6d929e101a865f9e4bf887ace9dbb2866617dcae`, published
`codex/pdf-checkpoint-prototype`. Work is isolated on `codex/q04-acceptance`.
Current phase: runtime adapter implemented and locally checked; see [RUNTIME-ADAPTER.md](RUNTIME-ADAPTER.md). Phase-one evidence remains historical and unchanged.
**Q04 runtime acceptance is NOT COMPLETE. No new Temporal/K8s trial was run.**
#44 remains the final acceptance gate; #45 owns calibration and #46 packaging.

Read [stage impact and evidence reuse](STAGE-IMPACT.md), then the
[executable acceptance plan](ACCEPTANCE-PLAN.md). `fixtures.json` pins the six
existing captured inputs, original Source Revisions and page mappings; it contains
no PDF/text/image payload. `audit.py` checks the actual production dependency
contract, producer equality, R3 seal, fixture bytes and optionally private Q03
artifacts. It has no cluster, subprocess or inference operations and refuses to
overwrite its output. Missing inputs/hash drift fail; omitting private artifacts
records null, never a successful private-artifact check.

## Reproduce preparation

From this worktree, with the retained environment and private fixtures available:

```sh
python3 tests/pdf_processing/q04/audit.py \
  --fixtures /private/tmp/t09a-fixtures \
  --private-full /private/tmp/q03-results-20260916-a \
  --private-matrix /private/tmp/q03-results-20260916-d/matrix \
  --out /private/tmp/q04-NEW-audit.json

export PDF_TEST_FIXTURE_ROOT=/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=src:/private/tmp/q02-deps:tests/pdf_processing/q02:tests/pdf_processing/q03
PDF_PYTHON=/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python
"$PDF_PYTHON" -m unittest discover -s tests/pdf_processing/q03 -p test_q03_compatibility.py
"$PDF_PYTHON" tests/pdf_processing/q04/run_suite.py
```

The full suite uses local models/rendering and owned subprocesses, including a
small scanned restoration fixture; it is not a six-fixture inference trial.
Existing process supervision requires OS process inspection. Do not run competing
local qualification suites concurrently. See `evidence/` for this run's outputs.
No production files, prior reports, failed trials or raw artifacts are edited.

## Current handoff

The six-fixture runtime adapter and full graph/oracle, mode, warm/resource/drain
checks are implemented. See [runtime commands and prerequisites](RUNTIME-ADAPTER.md)
and [second-phase validation](PHASE-TWO-RESULTS.md). `q04_runtime.py --help` is safe
without service access; runtime execution requires a new externally approved
capacity file. Main must review process versus Pod scope and topology first.

No live Q04 runtime trial, service pause, ticket closure, branch publication or
merge is claimed. The stage-impact/reuse decisions remain unchanged because this
phase changes only qualification harnesses, tests and documentation.
