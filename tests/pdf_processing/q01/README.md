# Q01 continuation implementation handoff

Baseline: `9ba0bab559f4248aaeb2d54b6b74c8e01c0e12b7`.
Branch: `codex/q01-continuation`, worktree `/private/tmp/q01-continuation`.
Authority: GitHub #48 and #47, plus the supplied Q01 handoff.

**Implementation and local regression are complete; real-service acceptance is
pending a coordinated capacity window. Q01 is not accepted or complete.** The
runtime driver has been typechecked but has not been executed. Do not inherit the
R3 runtime PASS, integrate as qualified, close #48, or unblock final qualification.

## Change

Opt-in `method.continuation` selects `column-edge-continuation-v1` and its exact
helper SHA-256. Absent selection retains upstream behavior. Unknown versions or
wrong implementation hashes fail explicitly. The instance-scoped predictor is
installed in fresh/capture and restored assembly; upstream package files are not
patched. Text, labels, input elements, captions and footnotes are not rewritten by
the selector. Inline joins remain upstream behavior.

See [source review](SOURCE-REVIEW.md) for each of the seven candidate removals and
the added continuation. Four removals and one addition are adopted. The three
legitimate inline algorithm joins are preserved. Overlapping alternative targets
and multiple owners are rejected. Geometry thresholds define a bounded opt-in
method, not a universal parsing contract.

`freeze_profile.py` makes a new profile version/release and binds the helper hash;
it refuses to overwrite an existing output. The retained Linux profile and its
hash are listed in `evidence/release.json`. It is **not runtime qualified**. An
accepted plan freezes the entire profile and producer inventory. Existing accepted
plans still require their original worker/package; the new worker must not claim
them. Historical source/checkpoint/result artifacts and main's dirty files were
not changed.

## Stage impact for main/Q04

| Stage | Effect |
| --- | --- |
| Parsing/group | Invalidated conservatively: method record, parser bytes and helper fingerprint change. Old checkpoints cannot be relabelled as compatible. |
| Assembly | Invalidated directly; corrected boundary policy affects grouping and reference numbers. |
| Selection | New assembly/parsed-result dependency propagates invalidation. |
| Required picture OCR | New selection/assembly inputs propagate invalidation; OCR recipe itself is unchanged. |
| Existing content evidence | New exact document/parsed-result dependencies require new evidence. No Q02 relation policy is added. |
| Final result | New dependencies require a new immutable complete registration, after existing required-work barriers. |

The edit to shared `compatibility.py` additionally invalidates every stage whose
producer projection includes it. A future helper-only change directly affects
group/assembly projections, then propagates through downstream operation inputs.
The executable identity test checks helper-only projection changes and rejects
reuse between the historical and corrected methods. Evidence-only reuse remains
the existing T07 contract; no source-bytes-only shortcut was added.

Shared-interface note announced in this task before implementation: add only the
method continuation field and group/assembly helper fingerprints. Q02 may overlap
on compatibility/profile files; main must reconcile producer/release identities.
No finalization, relationship schema, algorithm derivation or symbol policy change.

## Verification

Use the retained Python without installing packages into its observed environment:

```sh
export PYTHONPATH=src:/private/tmp/t01-type-deps
PDF_PYTHON=/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python
"$PDF_PYTHON" -m unittest discover -s tests/pdf_processing/q01 -p 'test_*.py'
"$PDF_PYTHON" tests/pdf_processing/q01/checkpoint.py /private/tmp/NEW-Q01-OUTPUT
"$PDF_PYTHON" tests/pdf_processing/q01/full_suite.py
node /private/tmp/t04-npm-cache/_npx/110e52990071af13/node_modules/pyright/dist/pyright.js \
  --typeshedpath /private/tmp/t04-npm-cache/_npx/110e52990071af13/node_modules/pyright/dist/typeshed-fallback \
  --project /private/tmp/q01-pyright.json src/pdf_processing deploy/pdf-processing/worker.py \
  tests/pdf_processing/q01/runtime.py tests/pdf_processing/q01/freeze_profile.py
```

Recorded results:

- Original real checkpoint tracer: RED, wrong margin target; `evidence/red.log`.
- Focused suite: 14 PASS, including source failure, lowercase/uppercase page and
  column transitions, chains, inline preservation, headers/containers, exact and
  overlapping target ambiguity, owner ambiguity, source immutability and identity.
- Full local suite: 24 PASS in 37.657 seconds, including the existing scanned
  fresh/capture/restore regression and T04/T05 tests; `evidence/full-suite.log`.
- Typecheck: 0 errors/warnings; `evidence/typecheck.log`. The first invocation
  needed the existing explicit typeshed path; three possibly-unbound variables
  were then corrected before the passing check.
- Real 12-checkpoint assembly: reviewed four-removal/one-addition delta; unchanged
  text/type/source-region multiset and table/picture/page payloads with caption
  references resolved; `evidence/checkpoint.json`. Full child-graph preservation
  is not inferred. The first payload comparison detected reference renumbering,
  not changed captions; `/private/tmp/q01-checkpoint-20260915-a` remains unused.

The first sandboxed full-suite launch could not inspect owned child processes.
Its suspended runner was explicitly reaped before the successful guarded run.
The successful run held `/private/tmp/data-ingestion-pdf-qualification.lock` and
reaped its owned descendants before releasing it. No shared service was paused.

## Remaining real-service gate

The capacity-window request is pending. Read-only inventory found the retained
`pdf-t09a-validation` coordinator, Temporal and object store. No model-heavy
Temporal/Kubernetes workload was submitted, and no deployment/storage was changed.

After capacity is coordinated, run `runtime.py` from an isolated immutable copy
of this producer with the frozen runtime-matching profile, original pinned PDF,
model cache, fresh private output directory, and fresh object prefix. It creates
distinct Workflow/Activity queues and versioned requests, preserves selected
original-source evidence, uses the real production Activities, checks the durable
consumer result/required OCR/evidence, and submits a checked-reuse request. It
does not import historical checkpoints as new registrations. Supply `--profile`,
`--pdf`, `--model-cache`, `--out`, `--prefix`, and the existing service endpoints.
Re-freeze the profile after any producer edit; never use stale release hashes.

Return runtime histories, request/release/producer identities and artifact digests
to main before declaring Q01 complete. Fresh/restored corrected output, affected
recovery behavior, full graph/table/image-child and wider fixture qualification
remain for actual verification and Q04's wider matrix. Q02/Q03 symbol and algorithm
work, broad layout upgrades, pushes, merges and ticket changes are outside this slice.
