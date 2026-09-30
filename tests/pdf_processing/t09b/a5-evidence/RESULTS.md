# T09b A5 controlled verification result

Run identity: `t09b-calibration-20260928-a5`. One execution, no retry.

## Result

A5 passed all 11 pre-inference gates and completed the fixed warm sequence:

| Trial | Business result | Registered pages |
| --- | --- | ---: |
| warm-0-06 | complete | 28 |
| warm-1-07 | complete | 15 |
| warm-2-08 | complete | 12 |
| warm-3-native | complete | 51 |
| warm-4-06 | complete | 28 |

All five results have `processing_complete=true`. `warm-proof.json` records 29
groups, parser PIDs 131 and 828, and exactly one recycle. This proves the
business sequence and parser-recycle behavior for A5, but it is not a complete
acceptance result because controlled worker shutdown failed before the
measurement contract, all-sample resource gate, traffic reconciliation and
terminal evidence could be finalized.

## Stop classification

After the fifth business result, `Host.stop()` invoked the T09b worker signal
helper for worker PID 112. The helper exited 1, so the phase recorded
`CalledProcessError`; the outer controller then classified the workload as
failed and stopped without retry.

The final independent process sample still contains PID 112 with start ticks
48872656, the exact command hash reconstructed from `worker-host.json`, and a
complete process reading. Worker-local samples continued after the failed
helper call. These records exclude an already-exited worker and PID reuse as the
cause. The old helper used a floating `psutil.create_time()` equality assertion
and a command assertion, but captured and discarded stderr. The exact failed
assertion is therefore unknowable from A5 and is not inferred.

The acceptance-tool defect is repaired after this retained run for the in-Pod
worker path used by A5/A6: worker identity now publishes Linux start ticks,
graceful and forced cleanup fence on that kernel identity, and helper stderr is
preserved. A focused regression checks the start-tick argument and propagation
of the real helper failure. A bounded check using the actual helper in the
existing Linux coordinator Pod also proved graceful SIGTERM, rejection of a
mismatched start tick without signaling, and identity-fenced force cleanup.

## Resource evidence

- Node samples: 1,422; maximum node full PSI avg10 0.00; minimum available
  memory 2,539,843,584 bytes; VM OOM kills unchanged at zero.
- Worker Pod samples: 1,417; maximum cgroup memory 2,837,409,792 bytes;
  maximum owned PSS 2,643,303,424 bytes; cgroup full PSI avg10 0.00; OOM,
  OOM-kill and OOM-group-kill counters unchanged at zero.
- Object service samples: 2,074; maximum memory.current 1,001,181,184 bytes;
  memory.events.max delta zero; maximum full PSI avg10 0.00; OOM counters zero.

The independent collector did seal a complete 1,417-sample attribution summary,
including bounded controlled/failure shutdown transition windows. The normal
measurement contract was not written, so those samples remain diagnostic input
and do not retroactively accept A5.

## Cleanup

The owned Deployment, source ConfigMaps and Pod were removed using recorded
identities. All 32 held historical Deployments remain at zero replicas, no owned
Pod remains, and restoration errors are empty. The object service identity and
health are unchanged. The Bound evidence PVC
`t09b-calibration-a5-evidence-20260928` is retained with UID
`2b995f1a-224d-4b6f-b833-cf79b6200ff3` because terminal evidence was incomplete.

Disposition: **business sequence passed; acceptance incomplete due to an
acceptance-tool shutdown failure**.
