# J offline verification

The original I reproducer was rerun before changes. The new regression command
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 python3 -m unittest test_pod_transport_j`
first failed with remote scratch disappearance and failed final export after the
live receipt gap. The same actual snapshot/mirror/controller cleanup code now
passes ten tests: scratch lifecycle, permanent-file deletion/truncation, live
gap rejection, independent stopped export, complete controller finally cleanup,
corrupt identity retention, multiple chunks, exact worker-subtree restriction
terminal inventory digest rejection and complete success-matrix finalization.

Before runtime, also run the existing stop regressions against J, complete CLI
arguments, fresh-process ConfigMap-projected reviewed-input validation, J
pre-inference gates, existing resource/UID cleanup and durable evidence tests.
Generated worker, source and runner manifests must equal their builders; verify
`--offline-check` and `git diff --check`, then independent code review.
The standalone I reproduction is retained unchanged as historical diagnosis.

The inherited interrupted-supervisor test additionally exposed a seal-order
mismatch: `sync_inventory` sorts Path components, while the verifier compared
whole relative strings (worker-1/stopped.json vs worker-1.log). J now verifies
the same PurePosixPath component order while retaining unique paths, exact
inventory digest, file size/hash and full mirror-set equality. Both failed and
successful terminal contracts are covered; no acceptance threshold changed.

Before review: 114 tests passed with the prototype Python environment:

```sh
PYTHONDONTWRITEBYTECODE=1 Q04_RUNNER_VERSION=j PYTHONPATH=src:tests/pdf_processing/q04:tests/pdf_processing/q02:tests/pdf_processing/q03 /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python -m unittest test_pod_transport_j test_pod_stop_regressions test_yolo_pod_cgroup_j_runner test_pod_preflight_j test_yolo_pod_cgroup_runner test_pod_durable_evidence test_pod_evidence_directory_d test_pod_remote_evidence test_cleanup_workflows
```

The generated offline manifest check and diff whitespace check also passed.
