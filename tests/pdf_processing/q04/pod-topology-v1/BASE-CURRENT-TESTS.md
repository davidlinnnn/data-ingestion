# Base/current local-suite comparison

This comparison uses the same macOS Python and dependency path for base commit
`a2716ef4dec3d0571e456a0a0028aa36cfc916ad` and the current worker-Pod runner.
It does not invoke Kubernetes, Temporal, object storage, inference or a model.

The interpreter is
`/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python`
(Python 3.12.13). `PYTHONPATH` includes the existing `/private/tmp/q02-deps`;
that resolves botocore 1.43.94, Pillow 12.3.0 and psutil 7.2.2 without installing
packages. Both trees used:

```text
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=.:src:/private/tmp/q02-deps:tests/pdf_processing/q04:tests/pdf_processing/q02:tests/pdf_processing/q03 \
/Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  -m unittest discover -s tests/pdf_processing/q04 -p 'test_*.py'
```

| Tree | Result | Explanation |
| --- | --- | --- |
| base `a2716ef` | 288 tests; 1 failure, 3 errors | The failure compares the consumed `yolo-attribution-b` manifest to the later lifecycle collector currently selected by `staged_sources()`. The three errors are macOS sandbox denials from psutil's `sysctl()` process enumeration in subprocess cleanup tests. |
| current | 324 tests; 0 failures, 3 identical errors | The historical test compares the unchanged manifest to an exact retained copy of the source selected by commit `1d72b0c`; its SHA-256 is `3dc682ea2aeea9cbcee62a2e83193358179b8892f3c8eb330896a0d4cf6f3982`. The same three sandbox errors remain. The additional tests cover the dedicated PVC topology, fsync/terminal/readback protocol, full/partial/mismatch faults, volume identity and permissions, export-independent cleanup, claim retention and API-uncertain disposition. |

The historical manifest was not rewritten. The current lifecycle collector hash
is `dfd94073e3503bac5d1fe7270a2876939084229898337082c66a9e437f1e55b1`, so the
old assertion failed because it selected a different source after lifecycle work,
not because retained `yolo-attribution-b` evidence changed.

The fixture-07 reviewed offline suite is independently green at 97/97 from the
prior preparation. The current durable-evidence, topology, transport and runner
focused set is green at 42/42.
