# AG source-review request

Status: **PENDING — no oracle or acceptance decision is created by this file.**

AG's current-lifecycle output is deterministic within the completed warm sequence,
but strict Q04 graph comparison rejects its Wiki06 and native documents. The
retained documents and references are the review inputs:

| Fixture | Retained reference SHA-256 | AG document SHA-256 | Text nodes (reference → AG) |
| --- | --- | --- | --- |
| Wiki06 | `a936ed723ca31098e6104560759e2bc130c66d94d4dd3cb6b8471f0c9bc1d263` | `5f00af22b9264c32462f006f4debadff20fe52051424b38c8f06e5e28404cb68` | 490 → 496 |
| native | `616f9e2a73f530de42e16f9b451356c7549d46f68563e5c9513a046c47bc6135` | `5bfdfd9c2ef629f99d397b6420c2d9ee92ae0d5b2336e36bb8afed19a45d27a5` | 1,119 → 1,145 |

The full raw documents remain under
`/private/tmp/q04-warm-pod-cgroup-20260922-ag/evidence/state/warm-pod-cgroup-ag/`.
The strict `graph-delta.json` and source-fragment correspondence analysis remain
under `/private/tmp/q04-warm-pod-cgroup-20260922-ag/delta-analysis/`.

Both fixtures preserve the exact source-region multiset: no source segment was
added or removed, and the per-page source-region counts match. Wiki06 has six
one-reference-to-two-current text components. Native has 29 changed source-fragment
components: 23 one-to-two text splits and six many-to-many regroupings. Therefore
this is not eligible for a general split-normalization rule.

A review decision must bind these exact PDF and JSON hashes, enumerate every
accepted component and prove its label, source ranges, order, parents, children,
captions and table/picture bindings remain valid. It must reject any component
whose graph relation changes semantic reading order. Only that bounded decision
may create a new versioned oracle for a subsequent fresh/restored/exact-replay
runtime. It must not alter the historical references, AG evidence, producer,
resource guards or acceptance thresholds.
