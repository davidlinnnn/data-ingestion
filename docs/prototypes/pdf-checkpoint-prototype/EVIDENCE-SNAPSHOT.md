# Experiment evidence snapshot — 2026-09-11

This snapshot fixes the follow-up Kubernetes recovery and performance experiment
code, deployment manifests, reports and compact evidence alongside the original
prototype. Its parent is the original local prototype commit `25ddbe6`.

- [Kubernetes verdict](k8s/VERDICT.md) and [run instructions](k8s/README.md).
- [Performance diagnosis](performance/REPORT.md) and [run instructions](performance/README.md).
- [Measured producer hashes](k8s/evidence-linux/code-manifest.json),
  [runtime/method identity](k8s/evidence-linux/linux-method.json), and
  [performance coverage verification](performance/evidence/verification.json).
- [Issue #30](https://github.com/davidlinnnn/data-ingestion/issues/30) tracks the
  conclusion and transition to implementation design.

The reports retain their experiment-time statements, including cleanup and the
fact that the experiment task itself did not commit or publish its results. This
snapshot is the subsequent evidence publication. The performance report explains
the overhead left open in the earlier Kubernetes verdict.

## What is retained

Git contains the measured implementation, environment descriptions, source/model
digests, histories, ledgers, comparison results, timings and selected visual evidence.
The producer hashes were checked against the files being published. All compact
JSON/JSONL files and Python syntax were checked; `performance/verify.py` passed
for all 24 recorded trials. Snapshot validation did not rerun Kubernetes experiments.

Large outputs remain local and ignored: `PROTOTYPE-wipe-me/linux-k8s-evidence/`
contains the exported 795 shared-store objects (353,320,944 bytes) plus baseline
and checkpoint material; `PROTOTYPE-wipe-me/performance-evidence/` contains large
performance outputs and logs. Source PDFs, model caches and container images are
not published in this Git snapshot. Their identities and reconstruction procedures
are recorded in the runbooks. Consequently this is immutable compact evidence and
reproduction code, not an independently archived copy of every raw artifact.

## Decision boundary

Option 3 is supported for the tested fixtures, configuration and failure points.
Proceed to bounded PDF implementation design while retaining fidelity and recovery
gates. Production HA, safe upgrades, broad document coverage and sustained throughput
remain open. Internal checkpoint artifacts do not define the canonical schema.
