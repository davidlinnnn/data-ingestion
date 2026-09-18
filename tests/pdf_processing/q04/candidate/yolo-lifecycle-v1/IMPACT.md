# YOLO lifecycle candidate impact

Candidate version: `q04-yolo-lifecycle-v1`.

The candidate bundle is separate from the frozen accepted bundle. Its immutable
local path is `/private/tmp/q04-inputs-yolo-lifecycle-v1`; the source remains
`/private/tmp/q04-inputs-option-a-v7`. Fixture PDFs, references, content reviews
and oracles are byte-identical. The producer and harness hash maps in
`inputs.json` are regenerated for the candidate; the source bundle is untouched.
The candidate bundle passes the same `prepare.verify_bundle()` used by runtime
initialization, including the candidate cancellation adapter.

| Changed source | Behavior | Direct stage identities | Evidence consequence |
| --- | --- | --- | --- |
| `supervision.py` | Owns a fresh-child handoff lock; reaps idle warm parser; blocks rebuild until fresh child exits | group, assembly | Old warm PID/recycle evidence is incompatible; group and assembly registrations cannot be transplanted |
| `execution.py` | Wraps restore child spawn, completion, exception and cancellation in the handoff | group, assembly | Old group/assembly producer identities are rejected |
| `compatibility.py` | Adds `supervision.py` to assembly dependency projection | assembly | A lifecycle change cannot reuse an old assembly identity |
| `parse.py` | Documents the enforced fresh-assembly lifecycle | group, assembly | Hash-bound producer changes conservatively with the behavior |

The full producer manifest SHA-256 is
`3aed8bf64671d51c0017717d0a6d6cea00c871c48bf3712cadfea7e55ad4eb80`.
The candidate `inputs.json` SHA-256 is
`d94912049083318876bc551c647c82e073c3c4b181aff9626e4984655d20f39d`.
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
