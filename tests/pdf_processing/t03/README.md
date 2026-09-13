# T03 recovery acceptance

The primary seam is a versioned PDF request through real Temporal workers and
shared MinIO to `parsed_ready` or an explicit failure. Required OCR/final processing
completion remains T04. These fixtures are recovery oracles, not a language or
extraction-quality benchmark.

Use only the isolated `pdf-t03-validation` namespace. Instantiate the T02 pinned
service/worker manifests with T03 names, bucket `t03`, prefix `final`, and distinct
`t03-workflows` / `t03-pdf` queues. Preserve prior evidence namespaces and PVCs.
The cached ARM64 Docling image is unchanged. Mount the current package, normal
worker entry, native profile and these drivers as ConfigMaps. During fault cases
only, point Activity workers at `fault_worker.py`. Use a new immutable ConfigMap name for each package revision, update both worker
volumes and wait for old Pods to disappear; producer identity is frozen at worker
startup. Updating a mounted mutable ConfigMap can temporarily mix old in-memory
identity with newly visible files. The final run uses t03-package-qualified. No model/package installation into measured runtime.

## Checks

- `verify_store.py`: real conditional writes/races, lost write response (transport
  fault injected *after* actual service acceptance), committed corruption/missing
  bytes/invalid manifests, invalid credentials/bucket, unavailable endpoint,
  divergence, inventory, prefix capacity observation and truncation.
- `verify_temporal.py`: real synchronous Activity threads remain alive after their
  start-to-close timeout. A differing retry wins registration; the old attempt
  reports divergence and returns the winner. Another late attempt publishes after
  its Workflow has failed: a later Workflow may reuse it, but the old Workflow
  remains failed. Lost Activity completion repeats no accepted output work.
- `verify_failure_seam.py`: production Processing maps configuration and committed
  integrity failures into permanent Workflow failures with exactly one attempt.
- `make_fixture.py <output.pdf>`: creates ten native pages with independent literal
  text expectations. Put this PDF at coordinator `/tmp/native-ten.pdf`.
- `run_faults.py <evidence-directory>` runs `verify_pdf.py` and force-deletes the
  Activity Pod when it observes the explicit fault marker. It exercises a real
  native page stage in the second group, an uploaded artifact before registration,
  and registration before Activity completion. The first group must be captured
  once; the second may repeat only when unregistered. A second full submission
  reuses all operations with zero upload bytes. Assembly must preserve all ten
  literal page strings with zero repeated page inference.

The fault wrapper is test-only. It does not alter source/method/operation identity
or implement production fault controls. Processing kill is observed after a native
page-stage event; because the tiny group can finish before external deletion, the
wrapper prevents its publication while waiting. This proves unregistered-group
recovery, not arbitrary machine-instruction kill coverage. Upload kill is between
artifact PUTs, not an interrupted individual network packet or multipart request.

Run T02 invalid/native/replacement/reuse acceptance against the same final package
and isolated services as the full regression suite. Record Pod UIDs, runtime images,
source/request versions, all package/driver hashes and outcome files. Fixed T02 and
prototype evidence are not edited. Run type checking with the pinned interpreter
and external Temporal/botocore type sources; keep those tools outside model runtime.

## Scope limits

The forced Pod-loss test is not graceful warm drain (T05), node/disk loss, storage
HA, automatic corruption repair, or GC. Orphans remain retained. A conditional
single winner does not prove producers are deterministic: diagnostics compare
complete attempted payload names/lengths/digests, including diagnostic artifacts.
The focused byte-producer harness is additional evidence for a living timed-out
attempt, not a substitute for the real PDF fault cases.
