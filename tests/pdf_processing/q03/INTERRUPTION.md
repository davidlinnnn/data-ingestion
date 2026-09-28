# Interrupted required evidence: prepared procedure

The OS hook and executable driver are ready. **Actual Temporal/shared-storage/K8s
interruption qualification is NOT RUN.** Local tests exercise the real production
evidence subprocess and finalization with in-memory S3 transport. This procedure
qualifies a killed evidence child, not worker/Pod loss, drain or process warm state.
Production source, dependencies, profiles and accepted request identities are not
patched by the hook.

## Preconditions and admission

Use a newly coordinated capacity window and the exact reviewed producer inventory
in `evidence/producer.json`. No prior service-pause authorization carries forward.
Record the actual Linux Python, image/Pod, namespace, Temporal endpoint, bucket and
reservation end time. Use an unused private prefix and nonexisting output directory.
Bucket versioning is required. Export the existing private credentials normally.

The driver requires one Activity slot and exclusive ownership of its process and
scratch directory. Hold the shared qualification lock and coordinate a cross-Pod
reservation externally. No other work may use this driver's worker process. The
hook fails rather than choosing among multiple evidence children or scratch paths.
`psutil` must be available and the process must be allowed to inspect and signal
its own children. A denied permission is a failed trial, not permission to broaden
process selection or signal another worker.

## Run exactly this bounded case

Use the qualified Linux interpreter and mounted fixture paths. Set `PYTHONPATH`
to the checkout's `src`, `tests/pdf_processing/q02`, `tests/pdf_processing/q03`
and qualified installed dependencies. The private Q02 baseline/native oracle
must be available via `Q02_BASELINE` and `Q02_SOURCE_ORACLE` when their defaults
are not present. This command is a template and has **not been executed on K8s**:

```sh
python tests/pdf_processing/q03/runtime.py \
  --case interrupted-evidence \
  --producer tests/pdf_processing/q03/evidence/producer.json \
  --pdf "$Q03_PDF" --out "$Q03_INTERRUPTION_OUTPUT" \
  --prefix "$Q03_INTERRUPTION_PREFIX" \
  --temporal "$Q03_TEMPORAL" --endpoint "$Q03_ENDPOINT" --bucket "$Q03_BUCKET" \
  --topology "$Q03_TOPOLOGY" \
  --interrupt-timeout 30 --timeout 180 --total-timeout 600 \
  --capacity-approved
```

Do not use `python -O`. The capacity flag acknowledges an externally granted
window; it grants no service-pause or scheduling authority. The default `--case
matrix` also contains this case (22 cases total). Standalone execution is useful
when the interruption case needs its own slot or a retained failed trial is retried.
Do not reuse an output directory/prefix after a failure.

## Observable sequence

1. Capture the fixed source into a new versioned object and seed plan, assembly,
   parsed result, page checkpoints and **empty OCR selection** under a unique
   case prefix. Resolve and retain the assembly registration and exact document
   bytes. This is deliberately seeded upstream work, not a native/OCR PASS.
2. Start an actual Temporal finalization Activity with one attempt. The hook
   rejects existing evidence/complete registrations and preexisting evidence
   children/scratch. It records parent PID, hook digest, target evidence identity,
   source/document digests and its observation deadline in `interruption/armed.json`.
3. Observe a **new direct child of this driver**, with exact command
   `[sys.executable, '-m', 'pdf_processing.evidence']`. Wait for the first source
   PNG's complete IEND chunk. The file's mere existence is insufficient: it can
   still be in the middle of encoding.
4. Send SIGSTOP to that process through a PID/creation-time-aware `psutil.Process`.
   Poll until stopped under the observation deadline, checking it remains a direct child. Validate scratch source and
   document digests and actually decode the first PNG. Retain source/document/
   process log and partial output bytes privately, with a partial-manifest.json.
   Then audit the full paginated registration listing and verify absence of
   evidence and complete publication. No partial artifact becomes a registered result.
5. Send SIGKILL **only to that identified child**. The production supervisor must
   reap it and remove its scratch. The Activity/workflow must fail with parser
   `execution_failed`, after an observed OS interruption. Record history, failed
   Activity count, the interruption observation and the complete-registration
   absence audit. Confirm the retained assembly registration is unchanged. An
   unrelated failure without the observed boundary is not an interruption PASS.
6. Submit a new Temporal workflow using the **same accepted plan, request, source,
   profile, producer, selection and required-work arguments**. No registration is
   deleted or patched. The same worker starts a fresh evidence interpreter; this
   is not a worker-process-restart claim. Verify successful evidence/final delivery,
   all four independent algorithm oracles, source attribution, unchanged assembly
   bytes and readable representation evidence.
7. Submit an exact finalization replay. Require identical final identity and
   contents, and exactly one `pdf-complete-*` registration in the isolated prefix.
   Only then write this case's `accepted.json` and the selected run's acceptance.

## Required retained evidence

- Top-level admission/driver/hook/producer hashes, topology and case selection.
- `assembly-before-interruption/registration.json` and its exact document bytes.
- `interruption/armed.json`, `observation.json`, `partial/` bytes and their hashes.
- `interrupted-handle.json`, `interrupted-history.json`, `interrupted-failure.json`.
- Initial recovery and final replay handles/histories, final/assembly/evidence/
  relationship registrations and artifact bytes, all four oracle scores.
- Explicit no-evidence/no-complete result after interruption, reaped-child and
  scratch-cleanup checks, unchanged assembly registration, and the single final
  registration after recovery. Preserve failed/non-successful trials separately.

## Failure and cleanup

If the first complete page cannot be observed within the deadline, the child
finishes too quickly, there are ambiguous children/scratch paths, input hashes
mismatch, source evidence is unreadable, or publication already occurred, **fail
this trial**. Never substitute an ordinary retry, force an expected result, increase
scope to another process, or overwrite failure evidence. Cancellation first cancels
and joins the watcher, including its diagnostic copy/storage audit, then cancels
and joins the attempt; an already captured target is killed and reaped. The storage
client uses bounded connect/read/retry settings. Joining an in-flight storage call
can extend cleanup beyond the observation deadline; reserve time for cleanup before
the capacity window ends. A hard termination of the driver is not qualified here.
The hook does not signal unrelated children or operate on Deployments.

On any infrastructure error or timeout, preserve diagnostics, request cancellation
of the owned workflows and verify their terminal state using recorded handles.
A failed history fetch may mask the original exception; absence of `accepted.json`
is not enough to infer cleanup. Confirm no owned evidence interpreter or stopped
child remains and no owned Running workflow remains before releasing the capacity
reservation. Restore only replicas separately authorized and recorded for this
new window. Retain all source/results and partial evidence; do not delete PVCs or
shared artifacts. Stop at the reservation end; reschedule if needed.

Local regressions cover real interrupted subprocess → no final → clean retry →
four-case final → exact replay, missed-boundary refusal, timeout without signaling
an unrelated child, refusal after evidence publication, delayed OS stop observation,
and cancellation during a bounded storage audit with retained partial hashes,
including overlapping hook and outer deadlines. Actual server histories,
shared-storage behavior and K8s cleanup still require execution in the new window.
