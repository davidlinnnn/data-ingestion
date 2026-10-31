# #131 Seam B: one paper through the real stack

Run 2026-10-31 on macOS arm64 (CPU only) with [run.py](run.py): Temporal CLI 1.9.1 dev
server (Server 1.32.0), the RustFS S3 stand-in from `tests/s3/compose.yaml`,
`tools/fake_admission`, and one `kp-processing worker --queue orchestration|inference` subprocess
per task queue (rerun after the queue split, [t2-queue-split](../t2-queue-split/README.md)) on
the DEV profile (`tests/profiles/paper-pdf-dev.yaml`: `docling-parse@1` only). Paper:
corpus index 2, `02-2603.02766v1.pdf`, 22 pages, sha256 `61cc0e44…a615` (third-party; not in
git). Raw numbers: [evidence.json](evidence.json).

| Case | What ran | Result |
|---|---|---|
| A | Uninterrupted run, fresh bucket | Complete in 9.2 s: 5 parse groups, assemble, inventory, finalize. [result-A.json](result-A.json): 22 page images, 2 picture images, enrichments empty, profile limitations. 13 reports, seq 1–13, prepare → parse (pages 0, 5, 10, 15, 20, 22 of 22) → enrich (0 of 0 items) → finalize, last one pointing at the result ([reports-A.json](reports-A.json)) |
| B | Same paper, fresh bucket; inference worker killed with SIGKILL 5.1 s in, with 2 groups registered; worker restarted | Complete. Groups 1–2 ran once (attempt 1); the in-flight group 3 ran again as attempt 2 after the 60 s heartbeat timeout; no other Activity repeated. `native`, `inventory` and `profile` of the result equal A's; the received report sequence equals A's |
| C | New request for B's document | Complete in 0.5 s; all 5 groups, the assembly and the inventory `reused: true` |
| D | A's start input again | `already started`, exit 0 (REJECT_DUPLICATE counts as success) |
| E | Report receiver stopped | Complete in 2.2 s; result registered. After the first report gave up (DEV budget 1 s), only the newest pending report was tried |
| F | Password-protected PDF; `adopted_version: paper-pdf@2` | Failure reports [failure-password.json](failure-password.json) (`cause: source`, `PASSWORD_REQUIRED`) and [failure-version.json](failure-version.json) (`cause: platform`, category `integrity`, `ADOPTED_VERSION_MISMATCH`); reports prepare running → prepare failed with the AIP-193 block and `manifest_ref` at the failure report |

Priority keys on one shared queue ([priority.py](priority.py), same dev server): one worker
with a single Activity slot runs 8 bulk workflows (key 4), and 2 normal ones (key 2) start
while the first bulk Activity runs. Positions of the two normal Activities in run order,
three trials each:

| Server setting | Trials | Note |
|---|---|---|
| default partitions | [2, 3], [1, 2], [1, 2] | in trial 1 a bulk Activity from another partition ran first |
| one read and write partition | [1, 2], [1, 2], [1, 2] | bulk runs in start order |

Priority is enforced per partition, so strict order needs one partition.

Not covered here: resource limits and the 64-page paper (V2, #80), Worker Versioning (V1),
and concurrency (V8). The remaining failure matrix (corrupt, page, size and pixel limits)
runs at Seam A in `tests/stages/test_prepare.py`.
