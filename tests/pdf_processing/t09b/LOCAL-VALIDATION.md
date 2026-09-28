# T09b local measurement slice

2026-09-28: six focused unittest cases pass with:

```sh
python3 -B -m unittest discover -s tests/pdf_processing/t09b -p 'test_*.py' -v
```

`storage_measurement.py` wraps the S3 client used by both Store and direct
Processing.read_source calls. Explicit request/activity/attempt context follows
asyncio.to_thread. Bodies retain their original context even when closed later;
observer traffic is separate. Success, failed PUT, partial GET, SDK retry count,
and unknown transfer sizes are distinguished. Records contain no payloads or
credentials. No changes were made to the production producer or historical runners.

The tests cover concurrent attribution, missing scope, context restoration on
failure, partial-read cleanup, repeat close, observer exclusion and refusal to
invent wire-byte totals from SDK retries. A grouping-aware verifier compares the
entire document/checks and requires business completion; missing pages or OCR
content fail. No output fields are normalized away.

This is not yet an integrated collector: the worker must install the wrapper and
scope every Activity, including prepare and enrichment, and stream records to its
retained evidence volume. A killed process may leave an unclosed read without a
terminal event; runtime reconciliation must reject incomplete measurement, never
treat absent events as zero. Raw threads do not inherit ContextVars automatically.
The measured body covers the existing read/close call sites, not arbitrary SDK
stream methods. The existing Store aggregate remains unchanged and must not be
used for per-request attribution under concurrency.

Outstanding before baseline admission:

1. Add an independently checked transport-attempt measurement source, including
   partial/failed transfers; the new wrapper reports application delivery only.
2. Measure in-flight buffering and unique checkpoint denominators without counting
   verifier/inventory reads as workload traffic.
3. Integrate into a fresh T09b launch contract, include all stages and retain
   interrupted measurement evidence. Verify real SDK behavior and cleanup locally.
4. Review the concrete source projection, topology window, deadlines, resource
   guards and cleanup before the first baseline. No runtime or topology change
   has been performed in this slice.

The checked prototype and q04-local Python environments lack boto3. These tests
use a deterministic client double and are not an actual SDK/network proof.
No dependencies were installed and no transport completeness claim is made.
