# Q03 runtime driver: prepared, NOT RUN

`runtime.py` is an opt-in actual Temporal/shared-storage seeded-finalization
matrix. Preparation accessed no services and submitted no workloads. It does not
modify production discovery, existing drivers, shared workers, or deployments.

Run only after externally coordinating a capacity window. Required CLI arguments
are `--producer`, `--pdf`, `--out`, `--prefix`, `--temporal`, `--endpoint`,
`--bucket`, `--topology`, and `--capacity-approved`. `--producer` is a reviewed
JSON manifest with a `producer` mapping of every actual loaded
`src/pdf_processing/*.py` basename to its SHA-256, matching `Processing.producer`.
Do not reuse a Q02 manifest after source changes. The driver verifies that mapping
before service access, records it in admission evidence, and checks for source
changes between cases. Freeze concurrent source edits before actual admission.
`--topology` must identify the actual host/image/Pod; host results do not qualify
Kubernetes. Credentials remain in the existing AWS environment.

Use the repository working directory `/private/tmp/q03-structural-symbols`,
`PYTHONPATH=src:/private/tmp/q02-deps:tests/pdf_processing/q02:tests/pdf_processing/q03`,
and `/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python`.
`-B tests/pdf_processing/q03/runtime.py --help` is safe offline. Do not use `-O`.
The pinned retained baseline must be available through Q02's `Q02_BASELINE`
(or its fixture default); `--pdf` must match the pinned AIMA derivative digest.
Output must not exist. The shared prefix must be nonempty and unused, and bucket
versioning must be enabled. Each invocation adds a UUID namespace and each case
uses a separate prefix and unique queue. Nothing is deleted automatically.

The shared local qualification lock uses `PDF_QUALIFICATION_LOCK` or
`/tmp/data-ingestion-pdf-qualification.lock`. It is not a cross-host/Pod lease.
Cases are serial with one Activity slot and no automatic Activity retries.
Per-workflow deadlines default to 900 seconds; the total local deadline defaults
to 7200 seconds. Local interruption requests cancellation, shuts down the Worker,
and stops owned evidence children. Storage calls have bounded transport timeouts;
synchronous calls may delay asyncio cancellation. A failed cancellation/history
fetch can mask the original error, but cannot produce acceptance. After an
infrastructure failure, verify remote workflow and owned process termination
before releasing the externally reserved capacity.

The matrix contains valid four-case delivery, fragmented delivery, one independent
release gate for every declared stream difference and every isolated symbol, and
missing-structure/corrupt-attribution cases. Gate cases mutate only the selected
profile observation's disposition. Valid and gate cases start without an evidence
registration and use production's supervised evidence child. Split and fault cases
publish an explicitly fault-injected copy of the valid child's retained artifacts
under fresh identities; these are not fresh rendering claims.

Every case seeds plan, parsed result, assembly, placeholder page checkpoints, and
an empty OCR selection. No native parsing, OCR execution, restored assembly,
full PDFProcessing request, mathematical equivalence, quality acceptance, or
canonical acceptance is qualified. Fixture method metadata is not a qualified
native-model profile; only the evidence renderer package version is matched.

Successful delivery requires all four independent Q02 oracle structure scores,
unchanged raw assembly bytes, retained original PDF, exact source attribution,
four representation bindings and readable evidence artifacts with recorded keys.
A second actual Temporal workflow must return the same final identity and final
record. Initial/retry full histories, profiles, versioned source references,
registrations, raw outputs, representation views and oracle results stay in the
private output directory. Expected failures must be integrity ApplicationErrors;
gates must specifically report `representation_release_gate`. Registration
absence is checked with pagination to exhaustion after workflow termination.
This is an observation in an isolated namespace, not a storage snapshot guarantee.

Per-case `accepted.json` is written only after that case passes; top-level
`accepted.json` requires the entire matrix. Admission, failure and history files
are diagnostics, not PASS evidence. Actual service compatibility, child execution,
shutdown, fault rejection and retry stability remain **NOT RUN** until admitted
execution succeeds. Only CLI help and offline syntax compilation were validated
during preparation.
