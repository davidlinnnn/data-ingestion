# I local validation

Required: red reproduction against immutable H, green I regression tests for
sample retention and real worker/log layout; terminal rejection preservation;
interrupted supervisor terminal seal; real process-group interrupt/reap;
complete CLI parsing and ConfigMap-projected runtime contract; generated source,
worker and runner manifest equality; existing readiness, cleanup, transport,
durable evidence and pre-inference suites. Results recorded before execution.

Completed before runtime: 104 tests passed with the bundled prototype Python,
including six exact stop regressions, I runner/preflight, historical shared
runner contracts, workflow cancellation, durable evidence and transport.
The projected workspace executes validate_reviewed_inputs in a fresh process;
full outer workload/preflight, initializer and matrix CLI arguments parse at
the actual entrypoints. Historical H red reproduction ran twice: four lost
sample assertions plus the exact NotADirectoryError. I's same loop passes.

Command (from repository root):

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests/pdf_processing/q04:tests/pdf_processing/q02:tests/pdf_processing/q03 /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -m unittest test_pod_stop_regressions test_yolo_pod_cgroup_i_runner test_pod_preflight_i test_yolo_pod_cgroup_runner test_pod_durable_evidence test_pod_evidence_directory_d test_pod_remote_evidence test_cleanup_workflows
```

The 32 held Deployment UIDs/zero replicas and cluster identity were independently
rechecked read-only before preparation. Runtime admission must recheck again.
