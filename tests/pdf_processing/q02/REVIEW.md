# Q02 review and handoff

Reviewed implementation against baseline `9ba0bab559f4248aaeb2d54b6b74c8e01c0e12b7`,
Q02 #49, specification #47 and the Q02 handoff. The live issues and all comments
were fetched at implementation start; both had no comments or contradictory
changes. Two independent review agents reviewed commit `d92f132`.

## Standards

No documented-standard violations. One minor duplication finding: the first
replay test repeated the path/digest/profile already provided by the shared test
fixture. Resolved by using `fixtures.document()` and `fixtures.policy()`, which
also ensures the original baseline digest is checked. The independently frozen
oracle code is intentionally separate from runtime derivation.

Final count: zero open findings; one minor finding resolved.

## Spec

No actionable implementation defect or scope creep found. The reviewer confirmed
the publication barrier, source/result/method attribution, independent region
counts, order/range checks, legitimate fragmentation and old-policy preservation.
One open qualification finding remains: the real Temporal matrix seeds upstream
fixtures and does not exercise a full native request, selected OCR engine, or
actual checked parse/assembly reuse. It is explicitly not end-to-end acceptance.

Final count: one open qualification finding. Do not close #49 or claim #44/Q04
acceptance on this evidence. The requested model-heavy capacity window was not
provided during this session; no shared service was paused or changed.

## Tests and exact commands

Run from the isolated checkout `/private/tmp/q02-relationships`.
Native test-only dependencies (`temporalio==1.20.0`, boto3) were installed into
`/private/tmp/q02-deps`; the shared prototype virtualenv was not modified.

```sh
PYTHONPATH=src:/private/tmp/q02-deps \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  -m unittest discover -s tests/pdf_processing/q02

PYTHONPATH=src:/private/tmp/q02-deps \
  PDF_TEST_FIXTURE_ROOT=/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/t06/run_unit_suite.py

node /private/tmp/t04-npm-cache/_npx/110e52990071af13/node_modules/pyright/dist/pyright.js \
  --project tests/pdf_processing/q02/evidence/typecheck-config.json src/pdf_processing \
  --typeshedpath /private/tmp/t04-npm-cache/_npx/110e52990071af13/node_modules/pyright/dist/typeshed-fallback
```

Results: Q02 11 tests pass (including 27 failure subcases at final publication);
full suite 21 tests pass, including real scanned-PDF restoration; Pyright zero
errors/warnings. Logs are in `evidence/`. The initial missing-module/profile tracer
and split-header replay failed before their implementations were added, then
passed. No broader model/package upgrade was made.

For the lightweight runtime matrix, local port-forwards connected Temporal
`17233:7233` and object storage `19002:9000` in `pdf-t07-validation`. Existing test
credentials were passed privately as AWS environment variables. Command:

```sh
PYTHONPATH=src:/private/tmp/q02-deps \
  Q02_OUTPUT=/private/tmp/q02-runtime-20260915-c \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q02/runtime.py
```

Final trial C passed all 29 scenarios: three successful deliveries and 26
required failures rejected before complete registration. It verified the exact
final producer hashes and independently scored BFS/uniform-cost delivery.

`evidence/runtime.json` records each workflow/run ID, unique queue, private storage
prefix, real Activity completion/failure counts, precise failure and successful
immutable final/relationship/evidence registrations. Full source, rendered pages
and document bytes remain private. Original trial A failed on internal `cref`
references; trial B validated the corrected fixture format; trial C uses the final
reviewed producer and scores delivered BFS/uniform-cost results independently.
Historical attempts and artifacts were retained.

## Impact / remaining qualification

| Stage | Change / evidence | Remaining |
| --- | --- | --- |
| Parsing / assembly | No parser correction; conservative dependency-contract change invalidates baseline reuse. Subsequent evidence-only operation contracts compare equal. Full scanned restoration regression passes. | Actual new-request fresh/restored/warm reuse in qualified runtime. |
| Selected OCR | Existing completion barrier remains before evidence; missing required OCR fails in real Activity. | Actual selected OCR engine completion for the relationship request. |
| Evidence | New policy and fingerprinted bounded helper in existing supervised child; real rendering and durable report delivery checked. | Full-request qualification under a published immutable release. |
| Finalization | Separate relationship registration and exact validation before complete; real success/unknown/failure/retry checks. | Interruption/recovery and full request routing. |

The shared interface is documented in `README.md`. Q03 owns symbol dispositions;
combining-mark cases stay unresolved. Main must reconcile the changed dependency
contract, profile validation and finalization with Q01, then qualify the combined
producer. No release was published, pushed, merged, routed or deployed; no ticket
was closed. The baseline continuation defect is not fixed by this branch.
