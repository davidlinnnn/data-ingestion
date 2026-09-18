# Proposed next runtime batch: YOLO fixture 07

This is a preparation plan, not runtime authorization. It proposes one new
process-mode matrix phase for the full 15-page YOLO fixture: fresh,
restored/new-request and exact replay. It does not include another Keynote/ACL
run, AIMA, WikiSkill, native, warm, invalidation, guard, drain or Pod work.

## Why this is the next batch

YOLO is the smallest fixture that has no reusable integrated-producer run. It adds
six tables with the retained complete 60-cell audit, nine captions, four required
OCR components and the source-scoped U+0002/discretionary-spacing disposition.
Keynote and ACL already have accepted Q04 runs. AIMA's 12-page Q03 run is reusable
after exact identity reconciliation, so repeating it now would close less new
evidence. WikiSkill is 28 pages and native is 51 pages.

Historical timing is used only to size the window: R3 fresh YOLO took 46.17
seconds and sampled 1,916,985,344 cgroup bytes; exact replay took 2.03 seconds.
Those measurements do not predict or bound this producer.

## Fixed identity and acceptance

| Item | Proposed immutable value |
| --- | --- |
| Fixture | `07`, all original pages 1–15 |
| Source SHA-256 | `e6bda9784cfd83fd38c92a1162731aa1ec3413dbe1505946611595bfe59f29ab` |
| Bundle | `/private/tmp/q04-inputs-option-a-v7/inputs.json`, SHA-256 `9e46ad75379dffed05c5e25ec36b22fdf0d680e30e7d2b298d5ac355d0e039f2` |
| Reference graph | `references/07.json`, SHA-256 `a3ac9eb345949cdc83423ba1ae38c794400e8f4f89061056c1102517b6a1e6a1` |
| Accepted source runtime root | `/tmp/q04-option-a-20260918-c` |
| Accepted source state | `state/config.json`, SHA-256 `2a3264316e0a859b2a490b3724af09c2df16959b35d9c8116b02e078f50f0636` |
| Accepted source prefix | `q04/option-a-20260918-c/` |
| New remote root | `/tmp/q04-yolo-matrix-20260918-a` |
| New store prefix | `q04/yolo-matrix-20260918-a/` |
| Semantic runner | `q04_runtime.py` at commit `6f16ec8`, SHA-256 `5fc631f0076001b75815901d610b974b99db52a50d2eb9b8a3b735ab3d109471` |
| Operational launcher | `tests/pdf_processing/q04/sentinel/run_yolo_matrix_a.py`, SHA-256 `c2937100736b61377ad1cd5b9230d6149e4946513fa3aff2afa72494d323ef18` |
| Proposed phase | `yolo-matrix-a` |
| Proposed local evidence | `/private/tmp/q04-yolo-matrix-20260918-a` |

The fixed launcher validates the accepted Option A state, complete ACL phase and
retained ACL request on its original route, then copies the frozen code and bundle
to the new exclusive root. It creates a new live-init state and source namespace;
it never copies registrations or overwrites an existing phase. It stages the
reviewed outer admission and cleanup modules by digest, holds the exact remote
reservation, runs the semantic runner only after admission, reserves the cleanup
tail on every exit and captures the owned evidence. Any change to the launcher,
semantic runner, bundle, reference, producer, packages, models, profile or source
state requires a new review.

The exact invocation after a new authorization is:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_yolo_matrix_a.py \
  --execute \
  --owner '<approved capacity owner>' \
  --approval-reference '<verbatim new YOLO fixture07 authorization>'
```

The launcher refuses a missing `--execute`, owner or approval reference. The new
remote root, prefix, capacity, reservation, release, admission, log, runner and
driver-lock paths plus the local evidence path must all be absent. A collision
stops before runtime and no path is removed for a retry.

Acceptance requires all three records to be complete and checked through storage:

- exactly 15 registered pages and full typed graph/source traversal;
- retained 281-item type inventory unless a source-reviewed graph delta is
  accepted first; six tables and the complete 60-cell oracle;
- all actual captions, furniture, PictureItem children and four required OCR
  registrations with readable evidence;
- the localized source disposition stays scoped to the reviewed cells, with no
  global control-character normalization;
- restored uses a distinct request, reuses checked group/assembly work, reruns all
  selected OCR and equals fresh completely;
- exact replay retains the fresh request, plan and final identity, reuses every
  recorded step and equals fresh completely;
- `quality_accepted=false` and `canonical_accepted=false` remain explicit.

Any new graph delta is retained and fails the window pending source review. It is
not accepted merely because fresh and restored agree.

## Capacity and time

Use one 1,500-second lease. Reserve the last 300 seconds for cleanup. Outer
admission observes at most 180 seconds and requires 60 continuous seconds with
MemAvailable at least 4.5 GiB and full PSI avg10 equal to zero. Keep the existing
per-case admission at 3 GiB for 60 seconds, the 1.5 GiB active memory floor,
4 GiB active cgroup ceiling, zero full PSI, zero OOM increments and maximum
three-second telemetry gaps. Retain 825 seconds for the runtime workload and 195
seconds for staging/verification. Do not lower a threshold or extend the lease in
response to a failure.

Before reservation, recheck coordinator container/boot/PID identity, VM and cgroup
OOM baselines, Python/packages/models, bundle/state/producer/profile hashes,
Temporal idle/health, object-store readiness, the global qualification lock and
the 32 historical Deployment UIDs at `replicas=0`, `ready=0`. A Docker/container
restart invalidates the recorded baseline and stops before admission. The runner
must not scale or restore those 32 Deployments.

Stop without automatic retry on any identity drift, path collision, failed
admission, positive full PSI, memory/cgroup threshold breach, OOM increment,
telemetry gap, worker/sampler loss, workflow timeout, consumer/oracle failure,
unexpected reuse, graph delta or insufficient cleanup reserve.

On every exit after ownership, stop/cancel only owned work, retain partial records,
histories, registrations and telemetry, prove owned processes/parser/scratch are
absent, verify no owned Running workflow or forbidden complete registration,
recheck Temporal/object health and all 32 held Deployments, release the exact
reservation and retain cleanup errors separately. The 32 Deployments remain at
zero; this batch never restores them.

## Process and Pod evidence boundary

This phase uses a Linux worker process against actual Temporal Activities and
shared object storage. A pass proves YOLO delivery/reuse/replay and its bounded
process telemetry. It does not prove warm lifecycle, worker replacement, Pod UID
replacement, CRI-container termination, emptyDir removal, general resource sizing
or deployment packaging.

Pod drain remains a separate decision. Its missing owned Deployment, shared
bundle/state/evidence paths, label/UID fencing, replacement readiness and
old-container/emptyDir observation must be prepared before any Pod-mode request.
No Deployment should be created for this YOLO matrix.

After a pass, merge only the emitted `fresh-index.json` entry for `07` into the
reviewed index map. Do not rerun fixtures 09/10. The next choice should then be
WikiSkill versus the AIMA identity/index reconciliation; native invalidation and
recovery remain separately budgeted.
