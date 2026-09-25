# Q04 runtime preflight — based on 18be1b3

**Decision: ready for main-session planning, NOT admitted for execution.**
Only read-only cluster/process/service/model checks and local preparation were
performed. No workflow was submitted, no inference run, no remote file staged,
no Deployment created/scaled and no service paused. Historical pause approvals
were not used. Scope remains the six fixed PDF fixtures and existing contracts.

## Snapshot findings (2026-09-16 UTC)

Inventory began at 13:56:48 UTC; runtime/services at 13:58:58 UTC; capacity spans
31 samples over 30.08 seconds. This is not the required 60-second admission window.

| Surface | Observed result |
|---|---|
| Context / coordinator | `kind-internal-a2a-vs6-local`; `pdf-t09a-validation/coordinator`; UID `39c4bf45-45ae-4646-8d7b-ec47b2c61785`; Ready, zero restarts |
| Linux / Python | Linux 6.12.76-linuxkit aarch64 glibc 2.41; `/experiment/.venv/bin/python` 3.12.13; exact frozen match |
| Python packages / models | **112/112 package versions and 17/17 model hashes match**, no extra/missing entries; metadata/hash reads only, no inference/model construction |
| Frozen method | Retained Q03 profile method matches local Q01 Linux base; five-page groups; continuation code hash matches. Full runtime option instantiation remains the later runtime method check, not a preflight inference claim |
| Producer | All **20 files** in retained `/tmp/q03-20260916-d/src/pdf_processing` match; default `/app/pdf_processing` has **12 differing/missing files**. Stage exact 18be1b3 code and explicitly set PYTHONPATH |
| Temporal | All 11 PDF namespaces healthy; completed Running queries report **0 running workflows** |
| Object storage | All 11 readiness probes return HTTP 200; target `t09a` bucket versioning Enabled; proposed prefix empty. This does not test writes |
| Process idle scan | 24 coordinator/activity/workflow Pods checked; no matching warm-child, parse, Q03/Q04 or supervisor process; no query errors |
| VM capacity | Total 7.748 GiB; MemAvailable **2.258–2.307 GiB**; full memory PSI avg10=0 throughout; global OOM remains **28 → 28** |
| Coordinator accounting | cgroup memory **498.96–506.18 MiB**; memory.max/high=`max`, swap.max=0, cpu.max=`max 100000`; no cgroup OOM event changes |
| CPU / disk | 18 CPUs reported by the shared Linux VM; final load averages 6.65/6.65/6.40; `/tmp` filesystem free 1,802,612,977,664 bytes (not a reserved quota) |
| Persistence | Target object/Temporal PVCs Bound (2 GiB/1 GiB declared requests); coordinator `/tmp` has no PVC and must be privately exported before Pod loss |

The three kind nodes expose the same underlying VM capacity; do not sum their
memory/CPU as independent hosts. PVC requests and filesystem free space are not
proof of dedicated/enforced quotas. Readiness and no running workflows are dated
idle observations, not exclusion of future work or independent object-store clients.

Closing inventory at 2026-09-16T14:09:19.843786+00:00 confirms all 65 Deployment
UID/replica pairs unchanged. No mutation was performed.

The proposed 3 GiB admission rule currently fails. [PAUSE-CANDIDATES.md](PAUSE-CANDIDATES.md)
lists exactly 20 candidate Deployments (T03–T07, four roles each), their UIDs,
current replicas/Ready counts, intended 1→0→1 changes and idle results. Main must
approve a fresh scope/lease and confirm no other clients before any pause. Do not
change application/reference-inventory services or widen the candidate set.

## Concrete sentinel handoff

[KEYNOTE-SENTINEL-PLAN.md](KEYNOTE-SENTINEL-PLAN.md) contains exact staging, init,
Keynote-only fresh/restored/replay commands, immutable paths/prefix, proposed
thresholds/time limits, stop/cleanup/capture procedure and expected verdicts.
`capacity.draft.json` is deliberately not executable approval. The private package
already exists locally; no files have been transferred to the coordinator.

Main decisions: approve the three-workflow Keynote sentinel and six-original-source
capture at init, choose an actual 20-minute capacity window/owner, approve or reject
the listed pause set, and arrange restore-on-every-exit before starting. Re-run
current read-only checks after any approved pause; insufficient capacity means abort.

## Pod-mode drain topology gaps (no Deployment created)

1. Coordinator has **no kubectl or Docker CLI**, and no Docker socket/node-access
   mount. Existing `Host.drain` needs Kubernetes UID operations plus kind CRI and
   old emptyDir inspection via Docker. Local macOS tooling cannot silently satisfy
   a Linux in-process host adapter's calls. Select and authorize a suitable Linux
   controller/tooling boundary before Pod mode.
2. Coordinator repo/bundle/state are container-local `/tmp`; current mounts are
   ConfigMaps and a service-account projection. There is **no shared writable
   repo/input/state/evidence volume** visible at identical absolute paths in both
   coordinator and a replacement worker. Define storage, access modes, node affinity
   and evidence durability; do not reuse object/Temporal PVCs as scratch.
3. No Q04 run-labelled Deployment exists. A future uniquely owned single-container
   Deployment must have `q04-run=<frozen init run_id>`, an idle parent, stable image
   digest/package/model fingerprints and `scratch` emptyDir mounted `/scratch`.
   Existing historical workers, zero-replica templates and `/app` code are not that
   ownership or image/code contract.
4. Need verify RBAC for read/exec and UID-preconditioned Pod deletion, plus node
   Docker/CRI inspection permissions, without granting broad service mutation.
   Coordinator API token presence is not proof of those permissions.
5. Need define resource requests/limits and the observation boundary. Current
   coordinator is unlimited; process-mode cgroup measurements do not prove worker
   Pod memory isolation, replacement capacity or loss of old runtime/scratch.
6. Need an approved separate drain lease, one Ready owned Pod with zero restarts,
   replacement scheduling deadline, old UID/runtime/emptyDir absence checks,
   continuous VM and segmented cgroup evidence, immutable capture and failure
   cleanup. A process sentinel cannot qualify any of these Pod-loss claims.

## Evidence and reproduction

`evidence/inventory.json`, `probe.json`, `processes.json`, `storage.json` and
`pause-candidates.json` contain sanitized metadata and timestamps. No credentials,
PDF bytes, extracted text or images are included. `evidence/package.json` binds
private code/input archive hashes and frozen bundle identity. `evidence/manifest.json`
binds these records; earlier Q01/Q02/Q03/T09a and Q04 failures remain unchanged.

Read-only reproduction, with a **new** local result filename:

```sh
python3 tests/pdf_processing/q04/preflight/inventory.py /private/tmp/q04-preflight-inventory-next.json
python3 tests/pdf_processing/q04/preflight/run_probe.py \
  --bundle /private/tmp/q04-inputs-local-v5 --out /private/tmp/q04-preflight-runtime-next.json
```

Probe uses package metadata, streamed file hashes, `/proc`/cgroup reads, Temporal
health/list queries and S3 versioning/list calls. It never starts a workflow,
imports a model, writes remote state, scales a service or sends a process signal.
The candidate process scan was also read-only; recorded process categories omit
command-line/environment values. Local syntax/archive verification does not replace
live sentinel acceptance.

## Local checks and review

Exact base archive plus private bundle verified after local extraction. Three
reproduction scripts pass AST/typecheck (0 errors/warnings); four command blocks
and the inner Linux shell pass syntax checks without execution. The draft capacity
file is confirmed rejected by the actual capacity validator. No production/runtime
files changed, and no PDF/model suite was run in this no-inference phase.

Independent Standards review found no actionable issue. Spec review confirmed
coverage and requested the pending evidence manifest; it is now present and
verified. The initial typecheck failure is retained alongside the final passing
log, and original runtime evidence remains unchanged.

Final independent Spec recheck verified all 13 evidence hashes and three script
hashes: zero residual findings. Standards residual findings: zero.

## Later YOLO attribution preparation

After retained matrix A crossed the unchanged 4 GiB guard, the offline
[`yolo-attribution-b/PLAN.md`](yolo-attribution-b/PLAN.md) prepared a fresh-only
diagnostic runner and strict external collector. It uses a new identity, retains
unknown/incomplete process reads, and makes no Activity-start claim from workflow
scheduling or external filesystem observations. This later preparation also
grants no runtime or capacity authorization.
