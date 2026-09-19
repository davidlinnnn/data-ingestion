# Q04 Pod topology v3 offline validation

No workflow, inference, Pod or PVC was started or created. The only cluster
operations were read-only `kubectl get` and `kubectl version` calls. The 32
historical Deployments were not changed.

## Passing checks

- Python compilation passed for the D topology, runner, workload, init,
  transport, preflight and evidence-directory modules.
- Evidence-directory contract: 5/5 tests passed using real local filesystem
  operations. Coverage includes exclusive `0700` creation, file and directory
  fsync, atomic rename, readback, capacity, and rejection of an existing path,
  symlink, foreign entry, wrong owner and wrong mode.
- One-shot pre-inference gates: 3/3 tests passed, including package/model/cgroup
  identity, source hash drift and the complete no-work-started result.
- D runner/topology: 8/8 tests passed, including local-path hostPath identity,
  mount-root versus application-directory semantics, ordering, cleanup labels,
  generated hashes and offline check.
- Historical C runner: 12/12 tests passed. Its runner manifest and source chain
  remain exact.

## Full Q04 suite boundary

The full local discovery ran 368 tests: 363 passed and 5 ended in known local
environment errors unrelated to this diff. Three imports lack `botocore` or
`temporalio` in the selected prototype venv. Two historical host-cleanup tests
were denied macOS `psutil` process-list access by the sandbox. The focused D and
C suites above have no failures or errors.

The D design remains `OFFLINE_READY_FOR_REVIEW`. A live Pod has not yet proved
that UID/GID 1000 can create the exclusive child on this exact kind hostPath.
That uncertainty is retained as a mandatory runtime gate, not inferred from the
local test result.
