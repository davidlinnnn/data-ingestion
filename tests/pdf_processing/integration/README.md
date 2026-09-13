# T03 / T04 / T05 merged integration

Accepted producer: `456e7c9` on top of the three merge commits. This gate supplements,
not replaces, the independent T03/T04/T05 evidence. See [VERDICT](evidence/VERDICT.md).
No shared evidence, objects or prior namespaces were deleted.

## Reproduction

Use the retained pinned Linux runtime and T04 validation resources. Copy the final
`pdf-t04-validation` coordinator's `/tmp/t04-fixtures` to
`/private/tmp/pdf-integration-fixtures`; compare all PDF hashes with
`evidence/attribution.json`. The old `t04-fixtures` ConfigMap contains exploratory
bytes and is not the qualified fixture source.

`python3 tests/pdf_processing/integration/setup.py` recreates worker/driver/package
ConfigMaps and isolated Temporal/MinIO in `pdf-integration-0913`. It derives Pod
mounts/image from the retained T04 deployments and coordinator, sets Pod60/SDK30/
TERM5/reap5, and uses the current checked-out package. Use a new namespace by changing
the `ns`/`NS` constants in setup/lifecycle for an independent rerun; retain old evidence.
Wait for all deployments before submitting work.

Copy qualified fixtures into coordinator `/tmp/integration-fixtures`, then run
`env T04_FIXTURES=/tmp/integration-fixtures /experiment/.venv/bin/python /driver/verify.py`
there. The verifier derives from T04 with new bucket/queues/output prefix names;
its environment variable remains `T04_FIXTURES`. Results appear in
`/tmp/integration-evidence` and include legacy v1 and repeat reuse.

Run `python3 tests/pdf_processing/integration/lifecycle.py` on the host. It creates
one fault worker at a time on private Activity queues, sends container PID1 SIGTERM,
observes exit/cleanup, then starts a normal replacement. It preserves Pod logs and
writes shutdown/result evidence. Its request driver uses the copied fixture path.
It stops the replacement after completion to release model memory.

Copy/run `second_read.py` in the coordinator after the normal suite. It copies a
valid frozen plan and parsed registration into its own prefix, uses the frozen
limits, removes a committed payload at its second read, then verifies production
Processing reports a permanent integrity error through actual Temporal (attempt1).
It does not alter original normal-run registrations.

Run the T04 and T05 unittest discovery suites in the pinned coordinator. Typecheck
uses Pyright with the existing Temporal/boto3 dependencies plus the pinned local
prototype venv in extraPaths, Python3.12; check `src/pdf_processing` and
`deploy/pdf-processing/worker.py`. No new dependencies are installed.
