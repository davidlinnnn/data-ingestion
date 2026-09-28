# T01 validation evidence

Baseline: `85925faa5b6167ee6e750fd02a0f3930d7ed8089` (#30).
Implementation: `84f199c` (#34), before documentation/evidence follow-up.

The historical document hashes come from the archived native/scanned Linux outputs.
They are regression expectations, not fresh snapshots to update after a failure.
The final real-service report records explicit source, method, producer and operation
attribution, plus the request/result references used in the isolated store.

Validation covers:

- Native 51-page and scanned two-page uninterrupted/capture/fresh-restore equality.
- Zero repeated page inference in complete fresh-process restoration.
- Real Temporal → grouped parsing → MinIO publication → assembly → component OCR.
- All 58 fixed figure labels recovered using the separately selected component.
- A fresh worker instance reuses the complete request without creating new objects.
- Exact historical Linux document hashes and unchanged historical prototype files.

This does not assert Pod-loss qualification of new worker lifecycle, long-lived child
safety, selective method compatibility, production storage HA or canonical acceptance.
Those remain with S1/T03/T05/T07 and the other design tracks.

Two-axis review found no blocking findings. Standards: one nonblocking judgement
about moving assembly input preparation out of operation dispatch, deferred to later
interface refinement. Spec: one nonblocking request for a reproducible historical
comparison gate, addressed by `verify_historical.py` and its runbook command.

The isolated local Kubernetes namespace is `pdf-t01-validation`, with bucket `t01`
and prefix `final`. It uses the cached `pdf-checkpoint-prototype:linux-v2` image and
the pinned MinIO/Temporal definitions from the frozen prototype. Raw artifacts remain
on that namespace's MinIO PVC; no historical/shared volumes were deleted. Large
parser outputs and logs remain on the coordinator at `/tmp/t01-run-final`.

Type checking used Pyright with the pinned local Docling interpreter and a temporary
copy of the existing Linux Temporal SDK for import resolution. The parser runtime's
installed package inventory was not changed to install checking tools.
