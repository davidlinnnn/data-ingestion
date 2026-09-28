# ACL Option A window c invocation failure

**ARGUMENT_VALIDATION_FAILED_NO_RUNTIME.** The authorization was consumed by one
launch attempt. The process exited 2 in argparse before entering the runner's
`main()` body. This is not a PDF, capacity, runner-precheck, fixture, graph or
oracle result. No retry occurred.

## Attempted command and cause

The fixed runner commit was
`56b3475f0ca2356bf0d18369a89d75c2b19dc1a3`; the worktree was clean. The
attempt used this shell shape:

```sh
Q04_APPROVAL_REFERENCE='main user approval of window c at reviewed commit 56b3475, fixture09 three modes only, 1500 seconds, stop on failure/no retry, 32 Deployments held closed' \
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/pdf_processing/q04 \
  /Users/david/work/data-ingestion/docs/prototypes/pdf-checkpoint-prototype/.venv/bin/python \
  tests/pdf_processing/q04/sentinel/run_acl_option_a_c.py --execute \
  --owner 'Q04 main task 01a0aa25-3a23-7fb2-b13c-6936f95ccbc7' \
  --approval-reference "$Q04_APPROVAL_REFERENCE"
```

POSIX shell expands command arguments before applying the temporary environment
assignments for that command. The final argument therefore expanded from the
caller's previously unset variable to an empty string. Argparse returned exit 2:

```text
run_acl_option_a_c.py: error: --owner and --approval-reference are required
```

The owner argument was present; the runner rejects the pair when either value is
empty. The error text therefore names both required arguments.

## Execution boundary

| Stage | Result |
| --- | --- |
| runner `main()` body | NOT_RUN |
| runner output-directory creation | NOT_RUN |
| coordinator/package/model/frozen preflight | NOT_RUN |
| Deployment and health preflight | NOT_RUN |
| remote root claim | NOT_RUN |
| reservation and capacity record | NOT_RUN |
| staging and live init | NOT_RUN |
| outer/per-case admission | NOT_RUN |
| fresh | NOT_RUN |
| restored/new request | NOT_RUN |
| exact replay | NOT_RUN |
| workflow and inference | NOT_RUN |
| runner cleanup | NOT_RUN; no owned work existed |

After the exit, local checks confirmed the planned evidence path remained absent
and Git remained clean at the fixed commit. A separate read-only coordinator
check confirmed the c remote root absent, c object prefix empty and the global
qualification lock free. The runner never queried or changed the 32 historical
Deployments and did not restore them.

There is deliberately no runner evidence archive, capacity record, accepted
record or cleanup report. Invocation evidence is retained separately at
`/private/tmp/q04-acl-option-a-window-c-invocation-20260918`; it is explicitly a
transcription of the local command/error and zero-side-effect observations. Its
three artifact hashes are recorded in `evidence/summary.json`.

## Corrected future launch

The thin `run_acl_option_a_c.sh` launcher requires an already exported nonempty
approval reference, then passes a fixed runner path, `--execute`, owner and the
complete reference as distinct argv entries. A local test ran that actual shell
launcher against a no-side-effect argv-capture stub and verified every argument.
Another test proves a missing export fails before the capture stub.

The first authorization is consumed. Because no c root, prefix, phase or evidence
path was ever created, the corrected plan intentionally reuses those objectively
unused identities. Reuse is contingent on a new explicit authorization and fresh
checks of Git, container/boot identity, OOM counters, health, held Deployments,
root/prefix/evidence absence and lock state. No real runner may start during this
preparation stage.
