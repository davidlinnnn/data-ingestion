# Verdict: supported for the bounded local Kubernetes recovery experiment

Measured 2026-09-11. Real Linux containers, real Temporal, real MinIO/PVC storage,
and **five deliberately deleted worker Pods** completed the previously missing gate.
This supports the checkpoint integration candidate for subsequent design. It is not
production adoption, a canonical schema, or a claim about arbitrary cloud failures.
The earlier [macOS/local verdict](../VERDICT.md) and [blocked preparation](PREPARATION-VERDICT.md)
remain historical evidence; neither has been silently rewritten.

## What ran

- The same versioned 51-page native paper and two-page synthetic scan from the
  original experiment; existing source/model digests were checked.
- Python 3.12.13, Docling 2.102.0, Linux ARM64/kernel 6.12.76-linuxkit, CPU with four
  inference threads. The Linux image uses Torch 2.14.0+cpu/torchvision 0.29.0+cpu,
  an explicit variant of the original package lock. Full package/model identity
  checks remain enabled; macOS checkpoints were not imported as Linux checkpoints.
- Final worker image `sha256:8ffaac39462e87d281274f92e4fa290aa905a054d40692646f1d3d42490f1ee0`.
  [Image identity](evidence-linux/image-v2.json), [method](evidence-linux/linux-method.json).
  The baseline coordinator used the preceding image with identical parsing code,
  packages and model files. The worker change corrected only experimental OCR
  reference resolution; strict reconstruction method comparison passed.
- Local kind v1.34.3, namespace `pdf-checkpoint-prototype`, one selected worker node.
  Temporal CLI 1.8.3/server 1.31.2 used its own SQLite PVC. MinIO used another PVC.
  Workers transferred artifacts through S3 HTTP; no worker-shared filesystem or
  local hard-link registration was used. This is not a production Temporal deployment.

## Recovery evidence

[Summary](evidence-linux/summary.json), [Pod deletions](evidence-linux/pod-deletions.jsonl),
[fault history](evidence-linux/fault-history.json), [fault ledger](evidence-linux/fault-ledger.json).
Five distinct Pod UIDs were deleted. Node CRI subsequently had no running containers
for those UIDs and kubelet cleanup was observed for each: [runtime observation](evidence-linux/runtime-observation.json),
[scoped kubelet logs](evidence-linux/kubelet-faults.log). Container records had already
been garbage-collected; API deletion alone was not treated as termination evidence.

| Deliberate Pod-loss point | Observation | Marker to accepted/reused output |
|---|---|---:|
| Group 1 registered, before Activity acknowledgement | Retry reused that registration; no new producer | 15.79 s |
| Page 7 persisted, group 6–10 unfinished | Retry recomputed only that unregistered group | 41.19 s |
| First shared object uploaded, group 11–15 not registered | Orphan object was ignored; group retried | 33.30 s |
| Reading-order invocation entry during assembly | Retry loaded saved groups; no page stages ran | 22.37 s |
| OCR engine initialized, before recognition | OCR Activity retried independently; parsing remained reusable | 18.19 s |

The last two faults are synchronized **stage-entry** points, not random interruption
inside reading-order/model instructions. The acknowledgement case kills the Pod
before it sends completion; it does not inject loss of an acknowledgement already
processed by the Temporal service. Heartbeat timeout is 15 seconds; observed recovery
also includes scheduling, replacement startup and any repeated work.

Normal and fault runs each produced exactly **13 registrations**: eleven groups,
assembly and image OCR. No producer started after its identity was already registered.
Observed preprocessing/layout/table stage input counts were **51 normal, 61 fault**;
ten extra inputs belong to the two unregistered groups. Page-assembly/checkpoint
persistence counts were 58 because only two pages of the interrupted first group had
reached that boundary. These are persisted completed-call observations, not exact
counts of unrecorded in-flight neural computation at the instant of death.

After completing the fault run, the MinIO Pod was stopped and replaced while keeping
its PVC. A fresh workflow then reused **all 13 outputs**, starting zero producers in
**0.523 s**. [Reuse history](evidence-linux/reuse-history.json),
[storage before](evidence-linux/storage-before-restart.json)/[after](evidence-linux/storage-after-restart.json).
This proves storage continuity across that Pod replacement, not node/disk durability.

## Fidelity and enrichment

Native and scanned fresh-process restoration matched every uninterrupted Linux
Docling JSON field, with zero repeated page-processing stages: [native comparison](evidence-linux/native-comparison.json),
[scan comparison](evidence-linux/scan-comparison.json). Normal and fault grouped
assembly were also compared in full against that Linux baseline before OCR.
All **188 files referenced by each run's 13 accepted manifests** were independently
rehash-checked after export. [Accepted artifact verification](evidence-linux/accepted-artifact-verification.json).

The real component image OCR recovered **58/58 scored labels** in both runs. Parsed
result digest, component reference, source coordinates, matching cached pixels,
model hashes, and caption content were checked. [Final OCR](evidence-linux/fault-ocr.json),
[actual crop](evidence-linux/figure-linux.png). The crop was visually inspected: the
same timeline region is present without the caption. This metric is normalized
substring recall, not character accuracy, precision, or a general OCR benchmark.
The original parser's documented table/heading/formula limitations remain; full
source correctness or all 51 pages were not manually re-audited here.

## Shared-store semantics

A real MinIO probe passed eight competing attempts, incomplete-output rejection,
accepted-result reconciliation, and a real uncompleted multipart upload remaining
unpublished. That multipart upload was then aborted. Two distinct Pods also raced
with different payloads and returned the **same winning accepted manifest**.
[Service probe](evidence-linux/object-service-probe.json), [Pod A](evidence-linux/race-a.json),
[Pod B](evidence-linux/race-b.json). The original in-memory probe is not the evidence
for these results. These semantics were tested on the selected MinIO image, not every
S3-compatible service.

The protocol requires immutable attempt objects and conditional manifest creation.
No-overwrite/no-delete behavior is an experiment assumption; production permissions,
retention and reconciliation policies remain design work. Orphan attempts were
preserved for inspection rather than silently promoted or deleted.

## Measured cost

Single trials, not averages. Conversion excludes import/export; process wall includes
them. Linux `ru_maxrss` was normalized from KiB to bytes in the evidence copies.

| Run | Conversion | Process/workflow wall | Peak successful child RSS |
|---|---:|---:|---:|
| Native uninterrupted | 42.56 s | 50.08 s | 3.13 GB |
| Native fresh restoration | 2.16 s | 4.59 s | 0.89 GB |
| Scan uninterrupted | 7.92 s | 10.70 s | 1.94 GB |
| Scan fresh restoration | 0.32 s | 2.47 s | 0.75 GB |
| Normal grouped workflow, including OCR | — | 112.25 s | 2.01 GB |
| Five-fault workflow, including OCR | — | 244.76 s | 2.03 GB |
| Reuse after MinIO Pod replacement | — | 0.523 s | No new children |

The raw native checkpoint is **53,022,659 bytes**. Normal accepted parsing/assembly/OCR
payloads total **76,402,784 bytes**. The normal path transferred approximately
**327.66 MB GET + 76.45 MB PUT**, including validation readbacks and result loading.
Successful S3 request time totaled **0.686 s GET + 0.647 s PUT** on this local setup.
Fault-run I/O counters exclude work lost with killed processes; they are not a complete
billable network total. [Child resources](evidence-linux/child-resource-summary.json).

The normal workflow is materially slower than whole-document conversion. It includes
sequential groups, repeated Python/model startup, validation, OCR and up to **one second
of publication polling per Activity** in this deliberately simple harness. Storage
request time alone does not explain the overhead. Reconstruction time is not an
end-to-end speedup claim. Persistent-model workers, larger batches, removing polling
floor and remote-network costs need separate measurement before an adoption decision.

## Failures retained and integration footprint

1. The inherited OCR harness hard-coded caption `#/texts/54`. Linux's same figure
   points to `#/texts/55`. The new scoped OCR script resolves the document-relative
   reference and verifies caption text/page; it does not weaken source/method checks.
   [Initial failure](evidence-linux/normal-driver.log), [history](evidence-linux/initial-failed-history.json).
2. A rolling configuration change briefly allowed an old worker to serve a new run
   on the same queue, mixing store prefixes. Dedicated queues and matched worker/client
   prefix configuration eliminated that contamination. [Failure](evidence-linux/normal-v2-driver.log),
   [history](evidence-linux/rollout-mixed-history.json). This is a concrete warning for
   subsequent deployment/versioning design; seamless code upgrade was not proved.

The original thin checkpoint adapter and Docling installation were not patched.
Additional code implements experimental storage, orchestration, fault entry wrappers,
reference validation and evidence collection. No stop condition requiring parser
core rewrites was reached. Checkpoint artifacts remain separate from Canonical Revisions.

## Limits, retained artifacts and next decision

Supported for these fixtures/configuration and the specified failure boundaries.
Managed-cloud deployment, cross-node/host/storage loss, random mid-inference kills,
network partitions, live cancellation, production HA/IAM, upgrades, noisy scans,
more papers and sustained throughput remain untested. The test-only blocking upload
callback is not a production cancellation implementation.

All **795 shared-store objects / 353,320,944 bytes** were exported before cleanup,
plus complete Linux baseline/checkpoints, into ignored
`../PROTOTYPE-wipe-me/linux-k8s-evidence/`. Small evidence is retained in `evidence-linux/`.
The dedicated namespace was submitted for removal after export; see
`evidence-linux/cleanup.json` for final status. Existing kind cluster/unrelated workloads
were not removed. Built images remain locally available; no commits, pushes or issue
messages were made.

Next return to design with the recovery boundary supported, but the measured normal
path overhead unresolved. Decide acceptable latency/cost, execution granularity and
worker reuse before production implementation. Define canonical schema/lifecycle from
consumer and provenance needs, rather than adopting this internal checkpoint format.
