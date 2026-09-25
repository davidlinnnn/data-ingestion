# YOLO lifecycle candidate graph-gate analysis

## Disposition

The retained `yolo-lifecycle-a` runtime remains **`FAIL_GRAPH_GATE`**. Fresh
processing completed all 15 pages and four required OCR components, but the
fixed full-graph comparison returned `SOURCE_REVIEW_REQUIRED`. The batch stopped
there as required: restored, exact replay, and every later fixture did not run;
there was no automatic retry and no fresh-index acceptance.

The complete retained delta is explained by two source-preserving
representations of table-interrupted cross-page paragraphs. This finding does
not relabel the failed runtime. It supports a narrowly bound, inactive
source-reviewed equivalence proposal for main-session review.

## Immutable evidence and reproduction

The offline analysis fails closed unless these identities match:

| Input | SHA-256 |
| --- | --- |
| retained runtime archive, 9,287,680 bytes | `5c183da78740cb68cc7114dc06a4e2a7bd890b17c7f7637dd69adc8495bb9bc9` |
| batch state | `f6b607f008354b4b69a62a36bd174bb3e157af18acebe43132d169d61d1686ce` |
| fixture 07 source PDF | `e6bda9784cfd83fd38c92a1162731aa1ec3413dbe1505946611595bfe59f29ab` |
| candidate `inputs.json` | `67eba79d6125c536ab728edb4f7d8ee070d8aead49384f4afc3a48c78267d420` |
| historical methods evidence file | `eb58ea3afd15952ef06390d62e3f5fc48f7f213d046e2ca210b11f247b8b83a9` |
| historical reference file | `a3ac9eb345949cdc83423ba1ae38c794400e8f4f89061056c1102517b6a1e6a1` |
| historical reference graph | `b270e1818bdeecf5f88cc83766c8ab3fa1e89a1586fb0cacbfbf049614a8c276` |
| retained actual graph | `80c435fc8dc171c6da52a1353195b7221ad2449a518c326efbb0193d9828587d` |

Run the analyzer against the retained paths:

```bash
PYTHONDONTWRITEBYTECODE=1 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
tests/pdf_processing/q04/diagnosis/yolo-lifecycle-a/analyze_graph_delta.py \
  --archive /private/tmp/q04-yolo-lifecycle-20260919-a/remote-evidence.tar \
  --runtime-root /private/tmp/q04-yolo-lifecycle-20260919-a \
  --batch-state /private/tmp/q04-candidate-batch-20260919-a/batch-state.json \
  --bundle /private/tmp/q04-inputs-yolo-lifecycle-v1 \
  --historical-methods tests/pdf_processing/t09a_r3/evidence/20260914-0b537d0-c/actual-methods.json \
  --output-dir tests/pdf_processing/q04/diagnosis/yolo-lifecycle-a/evidence
```

Running the original fixed `check_reference` against the same document and
reference deterministically raises `ValueError: unreviewed full graph delta`.
The diagnostic normalization is separate from that runtime gate.

Every loose runtime input used for cleanup and capacity conclusions is also
checked before it is read:

| Retained runtime input | SHA-256 |
| --- | --- |
| `cleanup.json` | `7bea7c849b2f757b851b703fe13deb867b98baf498e7171c83276a9da2bdcb85` |
| `health-after.json` | `6b17064be4e1a88b027c8bbd20dc89734fcef00ee5b767c9d871052df0e1ef66` |
| `held-services-before.json` | `d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4` |
| `held-services-after.json` | `d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4` |
| `lease-state.json` | `babe1b94a84ae8634db6eaeeef701eb0b829bba46099e8e365735fb8eecddd55` |
| `admission.json` | `c27adac4aae515d470421a5bd5997a8f9127882add1b9b5a11a62f11d0c1ba93` |
| `frozen-postcheck.json` | `daf464788f3a513509149709ddf93f0c8543fc6b5f9279be78e4fc68f24fcdfb` |

The analyzer rejects any mutation of these files. It also recomputes the
historical method payload digest and requires it to equal its recorded
`a37699…` key before comparing it with the fixed candidate inputs.

## Complete graph delta

The reference has 264 text nodes; the candidate has 266. Groups (5), pictures
(4), and tables (6) have equal counts. Exactly two historical text nodes are
represented as two candidate nodes:

| Historical node | Candidate nodes | Source pages | Candidate body positions | Intervening source order |
| --- | --- | --- | --- | --- |
| `#/texts/20` | `#/texts/20`, `#/texts/25` | 2 → 3 | 18, 23 | page footer, two page headers, `#/tables/0` |
| `#/texts/156` | `#/texts/157`, `#/texts/162` | 8 → 9 | 76, 81 | page footer, two page headers, `#/tables/3` |

Rendered source pages 2, 3, 8, and 9 show that each pair is one paragraph
continued after a table at the top of the next page. PDF text extraction also
contains all four fragments. Joining only each reviewed pair reproduces the
historical text and rebased provenance exactly. Parent, content layer, label,
geometry, and source order are preserved.

The four current-host render inputs for main's visual review are:

- `/private/tmp/q04-yolo-source-review-20260919-a/yolo-02.png`
- `/private/tmp/q04-yolo-source-review-20260919-a/yolo-03.png`
- `/private/tmp/q04-yolo-source-review-20260919-a/yolo-08.png`
- `/private/tmp/q04-yolo-source-review-20260919-a/yolo-09.png`

Their hashes and the render command are recorded in
[`evidence/source-render-paths.json`](evidence/source-render-paths.json). These
PNGs are local visual-review inputs, not runtime acceptance artifacts.

The candidate's conservative `column-edge-continuation-v1` method, SHA-256
`791e2ebef036d6f2468fb607162a135eecb3c4eaa056d4e35b1a81bffde49772`,
does not merge either pair because a table intervenes and the target begins
outside the top-quarter threshold. The second target begins at normalized
`0.253096`, just beyond `0.25`; the first begins at `0.632276`. Historical T09a
method `a37699da0a689066bd68fa9067e980272159afb7ae8554ac7dadefd471dabd36`
has no continuation attestation. Every non-continuation method field is equal.

The raw comparison reported changes in `body`, `groups`, `texts`, `pictures`,
and `tables`. The two extra text nodes shift 241 subsequent text refs, which
propagates into group, picture/caption, table, and body edges. After merging only
the two reviewed pairs and remapping their refs, all nine graph collections are
byte-equivalent under the fixed canonical projection. No source segments were
added or removed. Negative tests confirm that changed geometry, parent,
reading-order multiplicity, caption linkage, or table text remains a delta.

## Consumer and source checks

These checks inspect the retained completed document after the runtime failure;
they are evidence for review and are **not a runtime acceptance pass**:

- 283 graph nodes and refs, with no dangling refs or child cycles;
- the fixed 15-row, 60-cell source table oracle passes;
- all nine captions remain present and picture/caption linkage is equal after
  the narrow diagnostic normalization;
- all four required components were registered and returned `text_detected`;
- all 15 pages were registered, and the pre-graph consumer checks completed.

## Resource and cleanup boundary

Outer admission passed after 60.699 continuous seconds with at least
8,793,636,864 available bytes, PSI `0`, and OOM counters `0`. The active guard's
202 samples observed a maximum `memory.current` of 4,273,446,912 bytes, below
the fixed 4 GiB guard by 20,520,384 bytes. The independent 250 ms attribution
stream took 397 complete samples and observed a transient peak of
4,403,523,584 bytes, 108,556,288 bytes above 4 GiB. It also proves the intended
warm-to-fresh handoff and no warm/fresh overlap. The different sampling rates
explain why the active guard did not observe that transient peak; this run must
not be described as staying below 4 GiB.

The retained samples locate the only violation in group 3, while the same warm
parser PID serves its third sequential request. See
[`RESOURCE-DECISION.md`](RESOURCE-DECISION.md) for the complete phase, process
PSS, `memory.stat`, duration bound, baseline, cleanup, and preferred inactive
`max_requests=1` candidate. The new gate checks every complete 250 ms sample
against the unchanged 4 GiB threshold and requires both cleanup markers on the
final sample.

Cleanup passed with no owned processes, workflows, scratch, or errors left.
The reservation was released. All 32 historical Deployments retained their
expected UIDs and stayed closed; their before/after records are byte-identical
with SHA-256 `d078c3649a3c520eee4abfe0e1d35183a96514390b70bd373f9d564051e0e5f4`.
They were not restored.

## Recommended next disposition

Adopt, after main-session review, a fixture-07-only
`local_source_reviewed_equivalent_representation_oracle` bound to the source,
both graph identities, the current continuation method, and exactly the four
source regions recorded in
[`evidence/local-oracle-proposal.json`](evidence/local-oracle-proposal.json).
It must require exact normalized equality of the complete graph plus the table,
caption, OCR, and provenance checks, and reject any additional difference.

The proposal is now packaged for review in
[`../../candidate/yolo-equivalence-v1/`](../../candidate/yolo-equivalence-v1/).
Its independent validator is deliberately inactive and returns no runtime
acceptance. Main approval and a separate reviewed integration remain required.

The proposal is `PROPOSAL_NOT_ACTIVE` and has no acceptance effect. Do not
replace the historical reference, rewrite this runtime FAIL, infer a general
PDF-quality promise, or extend the equivalence to another fixture or method.
Any later accepted runtime also needs an explicit disposition for the complete
250 ms sample above the fixed 4 GiB measurement boundary.
