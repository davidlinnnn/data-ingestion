# ACL fresh resource v1 offline diagnosis

Status: **ACL acceptance remains FAIL.** This report explains the retained
failure; it does not update the reference, loosen an oracle, qualify the current
output, or change production parsing.

## Retained inputs

- Current document:
  `state/acl-fresh-resource-v1/fresh-09/document.json` in the retained runtime
  evidence, SHA-256
  `ff3cdcb6142e7046f5e248827548a1cd303f68c9317b2488d9dd251805c3f506`.
- Frozen reference: bundle `references/09.json`, SHA-256
  `aaa62538d423472fd4999675fdcd39501eaa11bce89d630843c8609177533c6c`.
- Captured source: fixture `09`, SHA-256
  `bd33fffb2c91f35225f5b89feb29a93013f4814558ac578bef000b632fd169bf`;
  processed pages 1–3 are original PDF pages 2–4.
- Historical authority: T09a R3 run `20260914-0b537d0-c`, `fresh-09`, which
  recorded the reference hash, 133 typed items, six formula occurrences,
  `TextItem` equation 2, two required OCR components, and its reviewed typed
  text/caption/order verdict.

The minimized red loop is `repro_graph_delta.py` plus
`evidence/page2-split-repro.json`. It deterministically reaches the production
consumer's existing `unreviewed full graph delta` rejection. The full retained
comparison is reproducible with:

```text
python3 analyze_graph_delta.py \
  --reference /private/tmp/q04-inputs-local-v5/references/09.json \
  --actual /private/tmp/q04-acl-fresh-resource-analysis-v1/state/acl-fresh-resource-v1/fresh-09/document.json
```

The checked result is in `evidence/full-semantic-delta.json`.

## Hypotheses and results

1. **One cross-column paragraph split caused the graph delta — supported.**
   The reference has one `#/texts/97` with two provenance regions. The current
   result has adjacent `#/texts/97` and `#/texts/98`, one per region. Joining the
   two current strings with one space exactly reproduces reference text and
   `orig`. Rebasing the second local charspan from `[0, 86]` to `[344, 430]`
   exactly reproduces both reference provenance records.
2. **Positional typed coverage amplified that split — supported.** The frozen
   oracle expects 68 page-2 items; current output has 69. Every current text node
   maps by exact source fragment to a reference node, with only the single
   2-to-1 mapping. The extra item shifts all later text references by one.
3. **The historical and current methods were identical — disproved.** Packages,
   models, platform, Python, options, and all other method fields are identical,
   but the historical R3 method has no continuation attestation. The current
   method adds `column-edge-continuation-v1` at SHA-256
   `791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772`.
   Their method hashes are respectively `a37699da...` and `e75b3287...`, using
   the same T09a R3 JSON identity convention.
   `compare_profile_provenance.py` rebuilds the field-level comparison, and
   `evidence/profile-provenance.json` retains the complete shared method payload.
4. **There was an additional loss, duplicate, parent change, or reading-order
   bug — disproved for this retained graph.** After the one diagnostic merge and
   reference renumbering, the complete graph projection is byte-equivalent:
   no differences remain in `body`, `furniture`, `groups`, `texts`, `pictures`,
   `tables`, `key_value_items`, `form_items`, or `pages`.

## Concrete split

Processed page 2 is original PDF page 3. Both current nodes have label `text`
and parent `#/body`. They occupy adjacent text positions 97–98 and adjacent body
reading-order positions 16–17.

| Side | Source box, BOTTOMLEFT | Text |
| --- | --- | --- |
| left, bottom | `(70.8565, 161.5741, 290.9490, 65.9758)` | starts “The knowledge distillation loss…” and ends “high-frequency” |
| right, middle | `(305.7513, 524.7973, 524.4271, 498.1005)` | starts “distillation losses…” and ends “Equation 3.” |

A 180-DPI rendering of original page 3 confirmed the same physical flow: the
paragraph ends at the bottom of the left column and continues in the right
column. The frozen source hash above, bounding boxes, exact text fragments, and
page mapping retain the reproducible evidence; the temporary rendering is not
part of the acceptance record.

The current continuation policy explains the split boundary. The left fragment
ends at normalized page bottom `0.9216`, but the right fragment starts at
normalized top `0.3766`. `column-edge-continuation-v1` requires a same-page
target to start in the top quarter (`bt <= 0.25`), so it intentionally does not
join this pair. The historical R3 method had no continuation override and its
upstream reading-order result did join it.

Raw graph comparison reports `body`, `groups`, and `texts`. `body` contains the
additional adjacent split edge; `texts` contains the split and subsequent
renumbering; `groups` differs only because later referenced text IDs shift by
one. The full semantic proof leaves no other collection difference. This is a
diagnostic conclusion, not an accepted normalization rule.

## Oracle and Q04 conclusions

- Exact full-graph equality remains required, so fixture 09 is **FAIL**.
- Page-2 full typed coverage remains **FAIL** at 69 current versus 68 frozen
  items. The six formulas, equation-2 type, source binding, graph completeness,
  and OCR evidence do not override that failure.
- The fresh resource slice remains useful only for resource calibration: its
  complete attribution stayed inside the 4 GiB candidate envelope with no PSI
  or OOM event. It does not qualify ACL, restored, or replay.
- The runner's historical overall verdict remains false. Existing result files
  and raw evidence are unchanged. Fixture expansion and issue #51 remain open;
  the 32 historical Deployments remain off.

## Owner-cleanup correction

The prior outer cleanup scanned every recorded workflow under the shared run and
treated old Temporal `NOT_FOUND` results as current cleanup failures. The narrow
correction now separates:

- exact current-phase ownership from `workflow-intent.json` and
  `workflow.json`;
- historical records, whose typed Temporal `RPCStatusCode.NOT_FOUND` is retained
  in `historical_missing` without changing any historical verdict;
- unrecorded prefix discoveries, which are reported as unexpected active work
  and fail closed without being signalled;
- transport, permission, unavailable, and string-only “not found” failures,
  which remain errors.

`Run.trial` writes an exact phase/trial/workflow intent before
`start_workflow`. This closes the submit-before-record ownership gap without
changing a request, producer profile, or production workflow. A current intent
that is missing in Temporal remains an error; cleanup does not reinterpret it as
stale history. Exact current running workflows can be cancelled and audited.
Historical or otherwise unowned running workflows are reported and left alone.
The future ACL resource runner stages this reviewed `q04_runtime.py` beside its
driver and places that runner directory first on `PYTHONPATH`; the frozen
producer tree and bundle remain untouched.

The other five sentinel runners changed only their outer cleanup call to identify
the phase. They are retained, already-consumed historical harnesses and do not
stage this pre-submit-intent runtime adapter. They must not be presented as having
submit-before-record recovery and are not approved for re-execution. A future
runtime identity must start from a separately reviewed runner after main decides
the ACL graph disposition.

The fake-client suite covers stale historical typed `NOT_FOUND`, a running
current record, the intent-backed submit/record gap, unexpected active history,
an unregistered running discovery, non-typed transport failure, current-owned
missing, foreign-run isolation, and cross-owner workflow-ID collision. The
fake-process suite covers exact current cleanup, retained historical/unowned
controllers, workers, parsers and scratch, PID reuse, duplicate owner records,
ambiguous controller identity, reparented parser retention, and exact terminal
proof before deleting scratch for an already absent worker. All tests are local and perform no live
Temporal, parser, inference, Kubernetes, or object-storage operation.
