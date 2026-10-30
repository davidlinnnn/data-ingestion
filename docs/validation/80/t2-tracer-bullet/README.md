# #131 Seam B: one paper through the real stack

Run 2026-10-31 on macOS arm64 (CPU only) with [run.py](run.py): Temporal CLI 1.9.1 dev
server (Server 1.32.0), the RustFS S3 stand-in from `tests/s3/compose.yaml`,
`tools/fake_admission`, and `kp-processing worker --pool cpu --tier normal` subprocesses on
the DEV profile (`tests/profiles/paper-pdf@1-dev.yaml`: `docling-parse@1` only). Paper:
corpus index 2, `02-2603.02766v1.pdf`, 22 pages, sha256 `61cc0e44…a615` (third-party; not in
git). Raw numbers: [evidence.json](evidence.json).

| Case | What ran | Result |
|---|---|---|
| A | Uninterrupted run, fresh bucket | Complete in 9.8 s: 5 parse groups, assemble, inventory, finalize. [result-A.json](result-A.json): 22 page images, 2 picture images, enrichments empty, profile limitations. 13 reports, seq 1–13, prepare → parse (pages 0, 5, 10, 15, 20, 22 of 22) → enrich (0 of 0 items) → finalize, last one pointing at the result ([reports-A.json](reports-A.json)) |
| B | Same paper, fresh bucket; worker killed with SIGKILL 5.6 s in, with 2 groups registered; worker restarted | Complete. Groups 1–2 ran once (attempt 1); the in-flight group 3 ran again as attempt 2 after the 60 s heartbeat timeout; no other Activity repeated. `native`, `inventory` and `profile` of the result equal A's; the received report sequence equals A's |
| C | New request for B's document | Complete in 0.4 s; all 5 groups, the assembly and the inventory `reused: true` |
| D | A's start input again | `already started`, exit 0 (REJECT_DUPLICATE counts as success) |
| E | Report receiver stopped | Complete in 13.4 s; result registered; each report gave up after the DEV budget (1 s) |
| F | Password-protected PDF; `adopted_version: paper-pdf@2` | Failure reports [failure-password.json](failure-password.json) (`cause: source`, `PASSWORD_REQUIRED`) and [failure-version.json](failure-version.json) (`cause: platform`, category `integrity`, `ADOPTED_VERSION_MISMATCH`); reports prepare running → prepare failed with the AIP-193 block and `manifest_ref` at the failure report |

Not covered here: resource limits and the 64-page paper (V2, #80), Worker Versioning (V1),
and concurrency (V8). The remaining failure matrix (corrupt, page, size and pixel limits)
runs at Seam A in `tests/stages/test_prepare.py`.
