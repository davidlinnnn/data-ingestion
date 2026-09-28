# YOLO matrix A offline preflight

[`evidence/offline-preflight.json`](evidence/offline-preflight.json) records a
local, no-inference execution of every generated pre-runtime probe in the fixed
launcher. The launcher remained byte-identical at SHA-256
`c2937100736b61377ad1cd5b9230d6149e4946513fa3aff2afa72494d323ef18`.

- The retained Keynote archive was opened without extraction. The fresh fixture
  `10` accepted record, config and fresh index were validated and hash-bound.
  The generated old-binding program then ran against the retained ACL snapshot. Its
  embedded accepted final reproduced the registered 18,102 bytes and SHA exactly,
  then bound request `q04-73615c42caa34c35b773568d4e2403bf` to the original
  ACL prefix/profile/release. The report computes that fixture, request ID, source
  key, source bytes, source revision and profile release all changed from Keynote
  to ACL. This is executable evidence of the source transition rather than a pair
  of fixture labels.
- The generated staging probe verified the fixed bundle, semantic runtime,
  fixture-07 reference, quality oracle, table oracle, method and producer.
- Production `q04_runtime.main(... phase=init)` ran with a memory-only versioned
  S3 stand-in and a temporary copied bundle. The generated init probe then checked
  the new run ID, new prefix, profile/queue/config schema, producer, method and
  release. Init returned before any Temporal client or worker could be created.
- The exact `--execute --owner ... --approval-reference ...` argv passed through
  the launcher's real parser and stopped at an intentionally pre-existing output
  directory, before lock acquisition, Kubernetes access or remote execution.

The evidence explicitly records `runtime_started=false`,
`workflow_started=false`, `inference_started=false` and
`deployment_changed=false`. It prepares the accepted YOLO plan; it grants no
capacity or runtime authorization.
