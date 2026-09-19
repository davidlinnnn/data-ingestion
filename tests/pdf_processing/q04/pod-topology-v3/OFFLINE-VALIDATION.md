# Q04 Pod topology v3 offline validation

No workflow, inference, D Pod or D PVC was started or created. Cluster
operations were read-only `kubectl get`/`version` calls plus a read-only probe
inside the existing coordinator Pod. The 32 historical Deployments were not
changed and their fixed UIDs and replicas/ready zero state were rechecked.

## Passing checks

- Python compilation passed for the D topology, runner, workload, init,
  transport, preflight and evidence-directory modules.
- Evidence-directory contract: 5/5 tests passed using real local filesystem
  operations. Coverage includes exclusive `0700` creation, file and directory
  fsync, atomic rename, readback, capacity, and rejection of an existing path,
  symlink, foreign entry, wrong owner and wrong mode.
- One-shot pre-inference gates: 4/4 tests passed, including package/model/cgroup
  identity, source hash drift, complete all-gate aggregation after multiple
  failures and the no-work-started result.
- D runner/topology: 10/10 tests passed, including local-path hostPath identity,
  mount-root versus application-directory semantics, ordering, cleanup labels,
  empty-stream growth, supervisor-publication classification, generated hashes
  and offline check.
- Historical C runner: 12/12 tests passed. Its runner manifest and source chain
  remain exact.
- The combined focused filesystem, preflight, D, C and historical transport
  suites passed 39/39.

## Full Q04 suite boundary

The full local discovery ran 371 tests: 366 passed and 5 ended in known local
environment errors unrelated to this diff. Three imports lack `botocore` or
`temporalio` in the selected prototype venv. Two historical host-cleanup tests
were denied macOS `psutil` process-list access by the sandbox; their complete
7-test file passed when rerun outside that sandbox. The focused D and C suites
above have no failures or errors.

The D design remains `OFFLINE_READY_FOR_REVIEW`. A live Pod has not yet proved
that UID/GID 1000 can create the exclusive child on this exact kind hostPath.
That uncertainty is retained as a mandatory runtime gate. The read-only probe
also found a known model gate failure in the unchanged pinned image: three
RapidOCR paths are absent and the total file count is 49 rather than 35. See
`READONLY-PREFLIGHT-RECONCILIATION.json`; no model or acceptance contract was
changed to hide the result.
