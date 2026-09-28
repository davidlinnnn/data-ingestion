# Q04 runtime adapter — phase-two handoff

**Implemented, locally tested, NOT executed against Temporal/K8s.** Production
remains exactly the 20-file Q03 inventory. No R3 pause authorization is inherited.
This supersedes the phase-one “adapter still required” status only. #51/#44 remain
unaccepted until actual trials and source-review gates pass.

## Execution and verification

`prepare.py` freezes a private portable input bundle. It verifies all six fixed
PDFs and originals, numeric physical-page maps, independent table/ACL/Keynote
oracles, source-hashed AIMA transcripts and retained Q01 checkpoint anchors. Graph
references are the five original R3 complete outputs and the accepted Q01 corrected
AIMA output, checked against their committed historical hashes. Full PDF/text/graph
payloads stay outside Git. The bundle binds producer and harness/oracle bytes.

`consumer.py` reads the real complete result through checked Store registrations.
It verifies source/plan/producer, every group checkpoint, complete document/page
coverage, full collection/edge/provenance traversal (including furniture, picture
children, captions, footnotes and tables), selected OCR identities/crops, readable
page PNGs and relationship binding. It applies each independent fixture oracle and
compares the complete typed graph with its pinned expectation. Ref serialization
`cref` versus `$ref` and absent optional nulls are representation-only comparisons;
text and mathematical symbols are not normalized. Historical table/Keynote oracle
whitespace allowances remain exactly scoped to those prior reviews.

Any unreviewed full-graph delta writes a private `graph-delta.json` and retains the
new document, then **fails qualification**, even if processing delivered a complete
result. It is not a publication-barrier defect by itself. Main must source-review
any additional continuation/graph delta before approving a newly versioned oracle;
the harness never regenerates expectations from the new output automatically.
AIMA independently verifies four structures and all eight Q01 conditions: four
false joins absent, one true join present, three inline joins retained. Source
anchors use original page/geometry/text, not corrected item numbers.

`q04_runtime.py` submits the unchanged PDFProcessing workflow and real production
Activities through unique queues and versioned shared storage. The qualification
worker hosts one frozen profile per queue and shares one WarmParser serially; it is
a test adapter, not #46 deployment packaging. No seeded parsing/OCR registration is
used for native runtime acceptance.

| Phase | Executable work and verdict |
| --- | --- |
| init | Validate bundle, current capacity acknowledgement, unused prefix and versioned bucket; capture originals; freeze profiles/queues/runtime config. No inference. |
| matrix | Fresh, restored/new request and exact replay for each selected fixture; each starts a new worker process. Native also runs evidence-only variation, real method invalidation (continuation removed under a new immutable release), rejects the old request on a changed profile, then replays it on its original profile. |
| warm | Wiki→YOLO→AIMA→native→Wiki, same worker and parser until request 20 recycle; exactly 29 group requests, two expected child generations. New captured source versions force actual group work. Full output equals Q04 fresh. |
| drain | New native request; observe five registered pages and active next-group child; stop only that child before graceful owned-worker drain. Replacement must retain the first group and show only 6–10 at attempt 2; all other groups attempt 1, 11 total, complete output equals fresh. |
| guard | Lose the owned sampler during the second native group; require fail-closed controller abort, owned workflow terminal, worker/child cleanup and no complete registration for this new request. Expected failure is separate from document success. |

Every successful complete case preserves all intermediate/final registrations and
raw result/history in its private case directory. New requests must rerun selected
OCR; zero selection is allowed only when the full pinned graph has no pictures.
Exact replay requires all recorded steps reused and the same final identity.
Method invalidation requires disjoint group/assembly identities, never copied
registrations or an equal-bytes shortcut. Required relationship interruption and
negative publication gates still have the unchanged Q03 trial-D proof plus local
regressions; this adapter does not relabel a group drain as evidence-child testing.

## Capacity and ownership contract

No runtime command has been run in this phase. A **new externally approved** JSON
capacity file and `--capacity-approved` are both required. The file needs `owner`,
`approval_reference`, Unix `starts_at`/`ends_at`, `admission_seconds`,
`admission_available_bytes`, `min_available_bytes`, `max_cgroup_bytes`,
`max_full_psi`, `max_sample_gap_seconds`, `max_replacement_seconds` and
`cleanup_seconds` (at least 120). These values must be chosen with the main session
and capacity owner; the harness does not turn historical measurements into bounds.
Admission requires the selected available-memory threshold and zero full PSI for
the whole admission period. Active guards check every recorded sample, VM/cgroup
OOM, memory/PSI, worker health and telemetry freshness. No new work runs in the
reserved cleanup tail of the approved window.

Future outer capacity-owner admission uses the independently testable procedure in
[`preflight/OUTER-ADMISSION-V2.md`](preflight/OUTER-ADMISSION-V2.md). It may observe
for at most 180 seconds while seeking one continuous 60-second 4.5 GiB/zero-PSI
interval. Ordinary misses reset that interval; fatal telemetry, OOM or ownership
conditions reject immediately. Observation consumes the same lease as the workload
and cleanup reserve. Its in-process POSIX alarm assumes cooperative local callbacks;
callbacks that catch `BaseException` or can defer Python signal delivery require an
external process supervisor before runtime use. This bounded pre-work wait does not
retry a workflow. Historical sentinel runners and their evidence are not rewritten.
The fixture-09-only runner and its 25-minute lease accounting are documented in
[`preflight/ACL-WINDOW-V2-PLAN.md`](preflight/ACL-WINDOW-V2-PLAN.md).
For this ACL window, the outer threshold is 4.5 GiB while the unchanged per-case
runtime admission remains 3 GiB for 60 seconds; the capacity record validates them
as separate fields.

Default **process mode** runs on a coordinated Linux host with `/proc` and cgroup-v2
telemetry. It starts/terminates only its owned qualification worker. This is actual
Temporal/shared-storage worker-process recovery; it does **not** qualify Pod loss.

Optional **Pod mode** (`--pod-namespace` at init) requires main to provision a new,
single-container owned Deployment labelled `q04-run=<init run_id>`. The adapter
never creates/scales Deployments or changes historical services. Prerequisites:

- Coordinator has Linux VM telemetry, kubectl access and Docker access to the
  existing kind nodes for read-only old-runtime/emptyDir checks.
- Worker and coordinator see repo, private bundle, Python path, model cache and
  writable state/evidence directory at identical absolute paths (shared volume).
- Pod has `scratch` emptyDir mounted at `/scratch`; images/package/model bytes must
  match the frozen runtime method. Its parent stays idle while the adapter executes
  its owned worker. Credentials remain in the existing runtime environment.
- Exactly one matching Running/Ready Pod, zero container restarts; new run label
  excludes historical workloads. The controller records full Pod/image/container
  identity. Drain deletion includes the exact Pod UID precondition.

Pod drain proves old API UID absent, old kind CRI containers stopped and old scratch
emptyDir absent before accepting replacement. VM telemetry continues during the
bounded replacement interval; old/new cgroup sample streams cover their live
intervals separately. The planned gap does not claim continuous cgroup observation.
Process mode has no Pod/CRI claim. Do not use Pod mode until these topology and
capacity prerequisites have been reviewed; no current topology readiness is claimed.

On failures, retain histories/partial artifacts, cancel only the owned workflow,
stop the owned worker and check for forbidden complete publication if required
work did not complete. Emergency force cleanup verifies PID creation time and
owned ancestry; it fails graceful qualification and retains a cleanup record.
The original failure is recorded before cleanup. Cancellation, task settlement,
worker stop, publication audit and history capture each retain independent outcomes;
one failure cannot suppress the remaining attempts. Any failed/unavailable remote
cleanup remains an explicit error, never a PASS. Remote ownership is checked even
when the local `kubectl exec` launcher has already exited; an uncertain cleanup
retains its ownership state for retry. Before ownership publication, cleanup uses
the exact unique launch command in the original Pod UID. A missing parent alone
is not complete cleanup: missing child/scratch proof retains pending ownership
and requires resolution before any subsequent qualification.
No PDF/PVC/object deletion or historical replica mutation exists in the adapter.

## Commands after main approves scope and capacity

Use a new private bundle/state/prefix; neither preparation nor trials overwrite
existing evidence. The following are templates, not executed workloads:

```sh
export PYTHONPATH=src:tests/pdf_processing/q04:tests/pdf_processing/q02:tests/pdf_processing/q03
export PYTHONDONTWRITEBYTECODE=1
python tests/pdf_processing/q04/prepare.py \
  --manifest "$Q04_FIXTURE_MANIFEST" --profile "$Q04_FROZEN_LINUX_PROFILE" \
  --oracles "$Q04_PRIOR_SOURCE_ORACLES" --checkpoints "$Q04_Q01_CHECKPOINTS" \
  --transcript "$Q04_AIMA_TRANSCRIPT" --references "$Q04_RETAINED_GRAPHS" \
  --out "$Q04_NEW_BUNDLE"

python tests/pdf_processing/q04/q04_runtime.py --phase init \
  --bundle "$Q04_NEW_BUNDLE" --state "$Q04_NEW_STATE" --capacity "$Q04_NEW_CAPACITY" \
  --temporal "$Q04_TEMPORAL" --endpoint "$Q04_ENDPOINT" --bucket "$Q04_BUCKET" \
  --prefix "$Q04_NEW_PREFIX" --model-cache "$Q04_MODEL_CACHE" --capacity-approved

python tests/pdf_processing/q04/q04_runtime.py --phase matrix --fixture 10 \
  --bundle "$Q04_NEW_BUNDLE" --state "$Q04_NEW_STATE" --capacity "$Q04_NEW_CAPACITY" \
  --name keynote-window-1 --capacity-approved
```

Start with Keynote as a complete-delivery sentinel. `--fixture` can repeat to split
matrix scope across approved windows; omit it for all six. Each partial matrix
writes `fresh-index.json`. For warm/drain/guard, `--fresh` accepts either one complete
matrix directory or a JSON mapping all required fixture IDs to their immutable
`fresh-<id>` directories. Merge the **indices**, never copy storage registrations.
Fresh records must match this run's producer/profile/source namespace. Each new
phase uses a new `--name` and current capacity file; frozen accepted profiles stay
unchanged. Then run `--phase warm`, `drain`, or `guard` with `--fresh` and the same
bundle/state. A phase PASS is not overall Q04 acceptance.

## Local validation scope

`run_suite.py` includes all existing PDF regressions plus Q04 source-oracle/graph,
mode/invalidation, resource/cleanup and checked-consumer tests. `test_controller.py`
uses an in-memory workflow transport plus actual checked Store/consumer logic and
real owned sleeping subprocesses. These prove harness behavior, not Temporal SDK,
K8s execution, model-resource bounds or operational readiness. Read-only R3 graph
and evidence JSON copies were fetched to new private local directories for tests;
no parsing, new workflow, service pause or cluster mutation was performed.
