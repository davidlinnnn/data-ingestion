# YOLO lifecycle candidate impact

Candidate version: `q04-yolo-lifecycle-v1`.

The candidate bundle is separate from the frozen accepted bundle. Its immutable
local path is `/private/tmp/q04-inputs-yolo-lifecycle-v1`; the source remains
`/private/tmp/q04-inputs-option-a-v7`. Fixture PDFs, references, content reviews
and oracles are byte-identical. Only the producer map in `inputs.json` changes.

| Changed source | Behavior | Direct stage identities | Evidence consequence |
| --- | --- | --- | --- |
| `supervision.py` | Owns a fresh-child handoff lock; reaps idle warm parser; blocks rebuild until fresh child exits | group, assembly | Old warm PID/recycle evidence is incompatible; group and assembly registrations cannot be transplanted |
| `execution.py` | Wraps restore child spawn, completion, exception and cancellation in the handoff | group, assembly | Old group/assembly producer identities are rejected |
| `compatibility.py` | Adds `supervision.py` to assembly dependency projection | assembly | A lifecycle change cannot reuse an old assembly identity |
| `parse.py` | Documents the enforced fresh-assembly lifecycle | group, assembly | Hash-bound producer changes conservatively with the behavior |

The full producer manifest SHA-256 is
`1e910b9109e959bb0ca21b4f81db9a2d933c1bd3e7591f37f38e4d2fa8fbfaa7`.
The candidate `inputs.json` SHA-256 is
`33909167ca5f1a79ab160da7d57fe2ae4bae38507fe21fa78877138cff13dda9`.
The exact file map is in [`MANIFEST.json`](MANIFEST.json).

Every new request must be initialized under a new object prefix and derives a
new `q04-*` profile release from the candidate producer and newly captured
immutable source versions. Existing plans compare the complete producer and
profile and therefore fail closed instead of being reinterpreted.

| Existing evidence | Candidate status | Reason |
| --- | --- | --- |
| Attribution-B failure and raw trace | retained diagnostic evidence | It describes the old producer and is never relabelled |
| YOLO matrix A acceptance rows | unproven | It failed before delivery under the old producer |
| Keynote and ACL accepted graphs | historical reference only | Their accepted producer/profile release differs from the candidate |
| Fixture 07 graph/table/caption/OCR oracles | reusable oracle inputs | Their bytes are unchanged; only a new candidate run may satisfy them |
| Q03 interruption/retry/replay | historical reference only | Lifecycle and producer identities differ |
| Fixed request-20 warm recycle sequence | invalidated | Assembly now intentionally ends each preceding warm lifetime |
| Guard, PSI, OOM and cleanup thresholds | unchanged | The candidate makes no capacity-policy change |

No canonical schema, LaTeX or general PDF-quality claim is added. This local
candidate has no runtime authorization.
