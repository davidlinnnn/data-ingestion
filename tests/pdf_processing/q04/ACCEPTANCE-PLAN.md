# Q04 executable acceptance plan

Status: phase-one local preparation. Runtime rows below remain pending except
explicitly reused Q03 evidence. Primary seam is the existing versioned processing
request through actual Temporal Activities and shared object storage; checkpoint
replay and in-memory transport are supporting seams only. No new service or
canonical schema is introduced.

## Fixed inputs and consumer assertions

Use exactly `fixtures.json`; verify SHA-256 before upload, preserve original page
mapping and source revision. No recutting/re-downloading to silently change bytes.
For **every** fixture, resolve final, assembly, selection, all selected OCR,
content-evidence and relationships through checked storage reads. Reconstruct the
full typed graph and parent/child/caption/footnote/table-cell references, including
furniture and PictureItem children; compare actual types and exact source regions.
Require every selected work item to be durable before `processing_complete`, with
quality/canonical acceptance false. Inspect intentional merge deltas against source
regions; only compare newly qualified fresh/restored/warm outputs for equality.

| ID | Scope | Additional independent oracle | First runtime disposition |
| --- | --- | --- | --- |
| native | Fixed 51-page paper | All 51 pages, complete graph/tables/furniture/pictures and required OCR | Pending fresh/restored; warm and drain representative |
| 06 | Full WikiSkill | Retained full table-cell audit, row/column spans and real captions | Pending fresh/restored/warm |
| 07 | Full YOLO | Retained full table-cell audit and localized control-character uncertainty | Pending fresh/restored/warm |
| 08 | AIMA original 99–110 | Four false associations removed, one true continuation added, three legitimate inline joins retained; four complete algorithms on 101/103/107/108, exact headers/body/captions, Q03 seven localized symbol dispositions | Q03 full fresh/reuse/replay/evidence reusable; pending integrated warm/recovery |
| 09 | ACL original 2–4 | All six reviewed equations, eq2 remains TextItem, exact typed text/captions and source-linked uncertainty | Pending fresh/restored/replay |
| 10 | Single Keynote export page | All 27 independently reviewed textboxes and source geometry | Pending fresh/restored/replay; preflight sentinel |

Outside AIMA's four declared regions, relationship discovery coverage stays unknown
with explicit `allow_unknown` and a durable reason. Do not copy AIMA's selected
regions to another PDF or promise universal algorithm discovery. Preserve existing
per-fixture source reviews; policy version and reviewed dispositions must be frozen
before submission. Missing evidence or malformed attribution is never an allowed
unknown. No LaTeX, mathematical equivalence, expanded language/scan support,
whole-book guarantee or canonical acceptance follows.

## Executable local and reused runtime cases

1. Run README's audit and focused compatibility test. The machine report must show
   all R3→integrated stages changed, evidence-only group/assembly unchanged, and
   helper changes invalidating the appropriate projections. The focused existing
   Q03 test rejects loading an old accepted plan under a changed policy and keeps
   legacy unsupported symbol cases unresolved.
2. Run `q03/run_suite.py` once. It includes Q01 retained checkpoint regression,
   Q02 independent oracle negatives/fragmentation, exact serialized-artifact binding,
   Q03 four structures, completion gates and real owned-child interruption/retry.
   These local checks are not Temporal/shared-storage acceptance.
3. Check Q03 trial D driver/producer and private artifact hashes. Reuse the actual
   successful full-request AIMA cases from trial A and all 22 trial-D cases for
   unchanged producer/policy/runtime. Keep A–C failures and seeded/full distinction.

After **new** capacity admission, existing AIMA drivers can be invoked directly:

```sh
export PYTHONPATH=src:tests/pdf_processing/q02:tests/pdf_processing/q03
python tests/pdf_processing/q01_q02/runtime.py --qualification q03 --case fresh \
  --profile "$Q04_PROFILE" --producer tests/pdf_processing/q03/evidence/producer.json \
  --pdf "$Q04_AIMA" --model-cache "$Q04_MODEL_CACHE" \
  --out "$Q04_NEW_OUTPUT" --prefix "$Q04_NEW_PREFIX" \
  --temporal "$Q04_TEMPORAL" --endpoint "$Q04_ENDPOINT" --bucket "$Q04_BUCKET" \
  --topology "$Q04_TOPOLOGY" --timeout 600 --capacity-approved
```

Only repeat this unchanged fresh case if an input/runtime change warrants it.
`--case reuse`, `exact`, and `evidence` run in separate processes, use the same
prefix and `--fresh-evidence "$Q04_FRESH_OUTPUT/accepted.json"`, with new output
folders. Exact uses the accepted request; other cases require new request IDs.
New request reuse does not imply OCR reuse. The Q03 `runtime.py` matrix invocation
and owned-child retry hooks are in `q03/RUNTIME-PLAN.md` and `INTERRUPTION.md`.
The capacity flag acknowledges external approval; it does not grant it.

## Cross-fixture runtime adapter work before admission

Do not execute historical `t09a_r3/*window.py` unmodified: they contain historical
paths, release/controller assumptions and service-pause operations. Reuse their
algorithms only in a new Q04 driver with new outputs, queues, prefix and release.
Preparation audit is executable today; the following runtime adapter is still
required before this plan can produce Q04 acceptance:

- Adapt the existing full-request driver to select all six pinned inputs and
  pre-frozen per-source policies, keeping the actual Activity/storage seam. Avoid
  transplanting seeded upstream results for native acceptance.
- Port T06's graph/source audit and T09a's table/ACL/Keynote checks to explicit input
  paths. Replace only historical AIMA fixed refs/CodeItem-pair expectations with
  Q01 reviewed continuation deltas plus Q03 independent four-structure oracle.
  Never apply old AIMA raw-item numbers to the corrected document. Preserve all
  exact text, symbol and caption checks; record additional merge deltas for review.
- Emit one result per fixture/mode with source, request, release/profile, method,
  producer, test/oracle hashes, workflow history and durable artifact inventories.
  A failed assertion yields a failed trial, not an overwritten rerun record.
- Fresh → checked restored/new request → exact replay for all six; use Q03 existing
  AIMA proof when identities match. Assembly/method-change request must reject old
  groups/assembly and produce new downstream IDs; never fake reuse by copying
  registrations. Replay an old accepted request only on its retained route;
  explicitly reject a changed producer/profile loading that old plan.
- Reuse R3's serial warm sequence Wiki→YOLO→AIMA→native→Wiki and request-20 recycle
  as the bounded workload. Record actual child PID/generation and group requests;
  equality is against Q04 fresh outputs. No concurrency/group-size tuning.
- Native drain: wait for five registered pages, interrupt only owned worker/Pod,
  resume on replacement; require only in-flight group 6–10 retried, retained
  checked groups readable, final equals Q04 fresh, old child/scratch absent.
  Requalify telemetry-loss guard/cleanup in the new controller. Do not inherit
  R3's measured durations as thresholds or claim Pod-loss from child-only tests.
- Preserve Q03 evidence-child failure-before-publication/retry/replay proof when
  unchanged; if the new driver alters that path, rerun its interruption case.

## Capacity, stop conditions and evidence exit

Coordinate namespace/Pod/image, runtime packages/models, endpoints/bucket, exact
start/end window, lock and cross-Pod reservation with the capacity owner. No pause
is pre-authorized. If pauses are necessary, present current exact Deployments,
UIDs, replicas and idle-work checks for a new decision; preserve data/PVCs.
Reconfirm admission/abort thresholds (historical 3 GiB/60 seconds, zero full PSI,
unchanged OOM are candidate guards, not universal sizing). Record VM available,
cgroup memory, PSI, OOM, sample gaps, restarts and child lifecycle continuously.
Abort on threshold violation, new OOM, telemetry loss, integrity failure or timeout.

On all exits cancel only owned work, retain partial artifacts/histories, reap owned
children, check no owned Running workflows remain, restore only newly authorized
replica changes to saved values/UIDs, verify affected Temporal/object-store health,
and release reservations. Keep failure, retry and cleanup records separately.

Return measured results and remaining unqualified rows to this main session for
integration review, then #44. No Q04 PASS until the cross-fixture and affected
warm/resource/drain rows have actual evidence and all new deltas are reviewed.
R3's 2.452 GiB sampled maximum and 1.583 GiB warm available minimum remain historical
observations; supported operating bounds for this producer are still unqualified.
