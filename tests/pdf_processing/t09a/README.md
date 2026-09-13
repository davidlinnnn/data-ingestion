# T09a long-workload qualification

Use the predeclared [plan](PLAN.md), fixed T07 baseline and existing local Linux
runtime. No public source PDFs, full parsed documents or crops belong in this folder.
The complete result seam is v3 required_evidence_v1; canonical_accepted stays false.

1. Run `prepare.py` with the retained prototype Python (PDFium). It verifies catalog
   and fixed native source hashes and creates `/private/tmp/t09a-fixtures`.
   The existing private T06 fixture manifest supplies the prior source-reviewed
   region policies; no old object references/registrations are reused.
2. Run `setup.py` to create only `pdf-t09a-validation`, using retained T04 Pod specs
   and local storage/Temporal templates. Run `bootstrap.py` **once** to copy/version
   originals and freeze `/private/tmp/t09a-profile.json`. Uploading originals again
   changes the frozen policy and is not compatible with already accepted request IDs.
3. Copy S2's `06-table-full-audit.json`, `07-table-full-audit.json`,
   `new-source-oracle.json` and T06 `quality-oracle.json` to coordinator
   `/tmp/t09a-oracles`. Copy `quality.py` and `collect.py` to `/tmp/t09a-test`.
4. All expensive work goes through `run.py`, which holds the shared host flock.
   `fresh native 06 07 08` starts a fresh worker per source; `warm` runs the declared
   mixed sequence with one converter until the configured 20-group recycle.
   The controller stops owned Activity Pods before releasing the lock. Never run
   another inference command outside the lock merely because a client disconnected.
5. `verify.py` records requests, progress and final results under coordinator
   `/tmp/t09a-results`; full JSON/evidence stays private. New source object versions
   force actual parsing for independent warm comparisons. Repeated trial names
   deliberately reuse an accepted request and must not be relabelled fresh runs.
6. Score delivered results with `quality.py SOURCE_ID TRIAL_NAME`. Source oracles
   predate the tested output. `collect.py` exports only attributable metadata and
   actual Temporal event/stage timelines to `/tmp/t09a-public`.
7. `sample.py` samples one-second cgroup v2 memory, CPU/pressure and child RSS plus
   scratch logical/allocated/free bytes. The Activity Pod has one container, so this
   cgroup covers all application processes (including its sampler); the host controller
   separately samples kubelet whole-Pod memory, including Pod overhead, about every
   ten seconds. Compare both series and record their independent sampling gaps. `memory.peak`
   includes Pod lifetime; `memory.current` maxima describe the sample interval.
   `summarize.py` reports observations; it does not automatically declare support.

Host-controller raw inventories stay under `/private/tmp/t09a-controller`. They
include API errors, host process metadata and node/Pod stats throughout trials.
Do not remove an interrupted observation to make an envelope look clean. A lock
coordinates T08/T09a only; record external host/cluster interference separately.

If an observation call fails, the controller continues recording errors. If the
experiment fails or is interrupted, it scales **only T09a Activities** to zero,
retaining flock until their Pods are confirmed absent. A pending Workflow may remain
queued with durable registrations; reconcile it explicitly before restoring workers.
After any controller failure, coordinate with the peer task and confirm remote
quiescence even if the flock is available. No cluster-wide destructive experiments.
