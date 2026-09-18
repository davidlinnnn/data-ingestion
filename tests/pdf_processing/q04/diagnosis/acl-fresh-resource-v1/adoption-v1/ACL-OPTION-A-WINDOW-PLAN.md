# ACL fixture 09 Option A 25-minute window

The execution identity is `acl-option-a-window-b`, local evidence is written to
`/private/tmp/q04-acl-option-a-window-20260918-b`, the remote root is
`/tmp/q04-option-a-20260918-b`, and the object prefix is
`q04/option-a-20260918-b/`. Every location must be absent before the reservation.
The live init creates a new run ID and frozen state; neither is copied from the
historical Keynote run.

The 1,500-second lease allocates at most 180 seconds to outer admission, 825
seconds to the workload, the final 300 seconds to cleanup, and 195 seconds to
exclusive staging, bundle verification and live init. Outer admission requires
60 continuous seconds with at least 4.5 GiB available memory and full PSI avg10
zero. Per-case admission remains 60 seconds and 3 GiB. The active sampled cgroup
ceiling is the reviewed 4 GiB candidate. VM and cgroup OOM counters may not
increase, telemetry gaps may not exceed three seconds, and the active memory
floor remains 1.5 GiB.

Only fixture 09 fresh, restored/new request and exact replay run. There is no
automatic retry. The matrix must verify the adopted exact graph, 40/69/21 quality
coverage, six formulas, equation 2 `TextItem`, two required OCR results, captions,
source evidence and full graph. Failure stops the matrix and preserves evidence.
Cleanup cancels only workflows named by the phase ownership records, stops owned
workers, removes owned scratch, captures the immutable evidence tree, releases
the exact reservation, confirms T09a health, and verifies all 32 historical
Deployments remain closed. It never restores those Deployments.

The exact local command is:

```sh
cd /private/tmp/q04-acceptance
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_option_a.py --execute \
  --owner 'Q04 task 01a0aa2d-e84d-71c2-9bed-42ff7d40b114' \
  --approval-reference 'Direct user authorization on 2026-09-18 for one Option A ACL fixture09 25-minute fresh/restored/exact-replay window; no retry; 32 Deployments remain closed'
```

A PASS is bounded fixture 09 evidence. It does not complete Q04, publish, merge,
push, or close #51.
