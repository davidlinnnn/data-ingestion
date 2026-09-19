# YOLO lifecycle candidate executable window

This plan grants no runtime, K8s, publication, merge or service-scaling
authorization. It fixes one future 1,500-second process-mode fixture-07 window.

## Exclusive identity

| Field | Fixed value |
| --- | --- |
| Phase and trial name | `yolo-lifecycle-a` |
| Coordinator root | `/tmp/q04-yolo-lifecycle-20260919-a` |
| Object prefix | `q04/yolo-lifecycle-20260919-a/` |
| Local evidence | `/private/tmp/q04-yolo-lifecycle-20260919-a` |
| Runner directory | `/tmp/q04-yolo-lifecycle-20260919-a/runner-yolo-lifecycle-a` |
| Driver lock | `/tmp/q04-yolo-lifecycle-20260919-a/yolo-lifecycle-a.driver.lock` |
| Candidate bundle | `/private/tmp/q04-inputs-yolo-lifecycle-v1` |
| Candidate inputs SHA-256 | `37a4cf0259d659d6ecdbce5a752d0bb8c6dc1a3679b1ade92d685a449858375c` |
| Producer-manifest SHA-256 | `a6501b471bd3193a7b0e890b386174a022aa9f1b63dca6432ae85e14b9f5af3d` |

All paths, the object prefix, reservation, capacity file and phase must be
absent before the launcher atomically claims the root. The generated run ID is
captured by live init and passed unchanged to the candidate driver.

[`OFFLINE-MANIFEST.json`](../../preflight/yolo-lifecycle-a/OFFLINE-MANIFEST.json)
binds the candidate bundle, four changed producer files, Q04 and deployment
workers, candidate adapter, collector, outer admission, cleanup and launcher.
The launcher copies every `changed_producer_files` and `changed_test_files`
entry over the frozen code tree before `prepare.verify_bundle()` and live init.
It cannot run the old runner with only a substituted producer.

## Fixed launch and budgets

After separate runtime authorization, the only permitted local entrypoint is:

```sh
export Q04_APPROVAL_REFERENCE='<verbatim later authorization>'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/pdf_processing/q04 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
tests/pdf_processing/q04/sentinel/run_yolo_lifecycle_a.py \
  --execute --owner 'main session' \
  --approval-reference "$Q04_APPROVAL_REFERENCE"
```

`$Q04_APPROVAL_REFERENCE` must contain the later explicit authorization; this plan
does not supply it. The launcher builds and shell-quotes the exact remote argv
recorded in the offline manifest, replacing only the reviewed
`q04-offline-candidate` placeholder with the live-init run ID:

```text
/experiment/.venv/bin/python
/tmp/q04-yolo-lifecycle-20260919-a/runner-yolo-lifecycle-a/yolo_candidate_window.py
--bundle /tmp/q04-yolo-lifecycle-20260919-a/inputs
--state /tmp/q04-yolo-lifecycle-20260919-a/state
--capacity /tmp/q04-yolo-lifecycle-20260919-a/capacity-yolo-lifecycle-a.json
--name yolo-lifecycle-a
--expected-run-id <live-init q04-* run ID>
--expected-prefix q04/yolo-lifecycle-20260919-a/
--attribution-interval-seconds 0.25
--attribution-gap-seconds 1
--capacity-approved
```

The remote workload wrapper is `timeout --signal=INT --kill-after=180s 825s`.
The 1,500-second lease reserves the final 300 seconds for cleanup. Before
launch it permits at most 180 seconds of outer observation and requires 60
continuous seconds with at least 4.5 GiB available, PSI full avg10=0 and
unchanged VM/cgroup OOM counters. Per-case admission remains 60 seconds at
3 GiB. Active limits remain cgroup memory at most 4,294,967,296 bytes (4 GiB), available memory at
least 1.5 GiB, PSI full avg10=0, telemetry gap at most three seconds and no OOM.
There is no automatic retry or threshold, group-size or concurrency change.

## Workload and comparison baselines

Only fixture 07 runs, in this order. Any failure stops later modes.

1. **Fresh** creates the baseline request, plan, registrations, artifacts and
   typed document. It must pass all 15 pages, the complete graph, six tables/60
   cells, nine captions, traversal and four required OCR registrations.
2. **Restored/new request** uses a different request ID and the same captured
   source artifact. Its complete typed document is compared with fresh.
3. **Exact replay of fresh** reuses the exact fresh request. Existing runtime
   checks require the fresh plan, registrations and artifacts to resolve
   unchanged; the candidate driver additionally rejects replay of the restored
   request.

The successful-workload collector contract requires no cancel marker. A
`cancel_requested` marker is required only when the actual
`q04_runtime.Run.cancel_owned` callback is invoked after failure or guard stop;
`cancel_completed` or `cancel_failed` describes that callback outcome.

The handoff marker comes from actual Q04 worker `samples.jsonl` rows where
`parser.handoffs > 0` and `termination_reason == fresh_child_handoff`. Process
birth/exit and 250 ms PSS samples independently require no sample containing
both an owned warm parser and owned fresh parse child. Local lifecycle tests
prove lock ordering, rebuild after a completed handoff, fail-closed reap,
parallel ownership and cancellation cleanup. The runtime matrix may fully reuse
work after fresh; it therefore does not claim to revalidate next-capture rebuild.

Warm sequence behavior is still unproven under this producer. Revalidating the
fixed request-20 recycle/warm sequence remains a separate #51 gate and is not
part of this window.

## Cleanup and offline gate

Every exit cancels and settles only phase-owned workflows, concurrently reaps
warm and fresh children, preserves scratch if an owned exit is unconfirmed,
captures evidence, releases the exact reservation identity, rechecks T09a
health and verifies all 32 historical Deployments remain at replicas=ready=0.

The single offline gate is:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/pdf_processing/q04 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
-m unittest tests.pdf_processing.q04.test_yolo_lifecycle_runner
```

Its first test calls `offline_validation_record()` and checks the complete
candidate staging map, bundle verification schema, live-init config schema,
exclusive identities, exact argv and deadline wrapper without contacting the
cluster or running inference.
