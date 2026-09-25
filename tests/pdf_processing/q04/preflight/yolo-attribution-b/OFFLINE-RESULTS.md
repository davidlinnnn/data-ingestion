# YOLO attribution B offline preparation results

## Result

`READY_FOR_MAIN_REVIEW / RUNTIME_NOT_AUTHORIZED`

The fresh-only fixture-07 runner, strict attribution collector, fixed source
manifest and 25-minute execution plan are complete locally. No Kubernetes or
Temporal command ran, no workflow or inference started, no reservation or remote
path was created, no producer/profile was changed, and none of the 32 historical
Deployments was restored.

## Prepared behavior

- new exclusive phase/root/prefix/output identity `yolo-attribution-b`;
- unchanged outer 4.5 GiB/60 s admission with at most 180 s observation;
- unchanged 3 GiB/60 s per-case admission, 4 GiB active shared-cgroup guard,
  VM floor, PSI/OOM and worker telemetry guards;
- 825 s workload allowance and final 300 s cleanup reserve inside 1,500 s;
- fixture 07 fresh only, no restored/replay, no automatic retry and no acceptance
  claim;
- 250 ms same-cgroup process attribution with PID/start-tick fencing, double
  enumeration, owned/shared classification, current RSS/PSS, `memory.current`,
  `memory.stat`, `memory.events` and `memory.pressure`;
- explicit unknown/incomplete values for read, identity, coverage and gap
  failures; any incomplete sample keeps the whole measurement incomplete and no
  missing PSS is converted to zero;
- an ordered baseline, external assembly-state observation, cancellation record
  and post-cleanup sample; missing or out-of-order markers are incomplete, with
  marker meanings limited to directly observed facts;
- per-sample and aggregate collector wall/thread-CPU/output cost, plus explicit
  limits on isolating in-process collector memory;
- identity-fenced owned cleanup, retained evidence and verification that all 32
  Deployments remain closed.
- committed-manifest enforcement before remote staging, immutable collector
  output after a stop timeout through a committed spool boundary, and
  token/PID/start-tick/lock-inode reservation reaping after release-write or
  wait failure.

The collector does not claim that an assembly Activity started from a scheduled
event, that `merged/` reveals the exact materialization start, or that a fresh
parse child necessarily received `mode=restore`. Exact internal markers would
require a separately reviewed producer hook and new hashes.

## Local validation

Focused offline suite:

```text
31 tests passed
```

This includes fourteen synthetic collector tests, twelve runner tests and five current
acceptance-matrix tests. It covers birth, exit, PID reuse, unreadable PSS,
same-cgroup shared processes, transition coverage that stays incomplete,
persistent incomplete coverage, required marker presence/order, collector gap,
bounded stop and immutable output, post-cleanup sampling, exact fresh-only argv,
capacity budgets, exclusive identities, fixed-manifest rejection, both
reservation-release failure paths, lost acquisition acknowledgement,
flush-boundary JSONL/summary atomicity, baseline/periodic partial writes and
`python -O` resistant runner checks.

Compatibility suite for the reused ACL collector/runner and retained YOLO matrix
runner/result:

```text
30 tests passed
```

Full Q04 discovery ran 187 tests: 182 completed successfully and five unrelated
environment-dependent tests could not run in this local sandbox. One needs
`botocore`, two need `temporalio`, and two existing host-cleanup tests require a
macOS `psutil` process-table `sysctl` denied by the sandbox. There were no test
assertion failures after regenerating the fixed source manifest. The focused and
compatibility suites above cover every changed module without those dependencies.

`git diff --check`, Python syntax compilation and JSON parsing pass. The source
hash table in [`OFFLINE-MANIFEST.json`](OFFLINE-MANIFEST.json) matches the current
runner staging set; [`PLAN.md`](PLAN.md) contains the same hashes and exact future
command. Any source edit requires regenerating both records before review.
