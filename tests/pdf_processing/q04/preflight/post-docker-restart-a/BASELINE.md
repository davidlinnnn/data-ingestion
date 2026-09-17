# Q04 post-Docker-restart runtime baseline

This is a read-only baseline for preparing a later ACL fixture 09 window. No
workflow, inference, reservation, capacity lease or Kubernetes mutation was
started while collecting it. The pre-restart trials and their raw evidence remain
unchanged.

## Docker and coordinator identity

Docker Desktop was restarted after its memory setting changed from 8,192 MiB to
12,288 MiB. At the 2026-09-17 14:12:38 UTC probe, Linux reported MemTotal
12,232,696 KiB and MemAvailable 9,612,192 KiB. Full memory PSI avg10/avg60/avg300
were all zero. The coordinator cgroup used 2,166,738,944 bytes; its max/high were
`max`, swap max was zero, and every cgroup memory event counter was zero.

The Kubernetes Pod UID was preserved across the restart, but the container
identity was not:

| Field | Post-restart baseline |
| --- | --- |
| Pod UID | `39c4bf45-45ae-4646-8d7b-ec47b2c61785` |
| Container ID | `containerd://75d02af07009f1d7152d6a68958cee5f43508ec1dd0ae327142a42db5e429ca5` |
| Restart count | 1 |
| Container start | 2026-09-17 13:46:12 UTC |
| Hostname | `coordinator` |
| Linux boot ID | `c01b81ac-b0fd-4ce6-8cda-f0da74b9bbd3` |
| PID 1 / start ticks | `1` / `733` |
| VM OOM-kill baseline | 0 |
| cgroup OOM-kill baseline | 0 |

The new runner fences all of these lifetime facts before acquiring a reservation.
The VM baseline is explicitly supplied to the admission adapter as zero. A
digest-staged telemetry guard plus `PYTHONSAFEPATH=1` gives that guard import
precedence for direct controller and worker script entrypoints, applying the same
zero baseline to every per-case runtime. The adapter's legacy default remains 28
so the consumed v2 runner is not reinterpreted.

## Restored frozen state

Both restored Q04 roots were compared with the verified archive using
`--keep-old-files`. The recovery report checked 36,593 recorded paths: 4,400
differences were Python bytecode caches and there were zero non-bytecode
differences. The source archive is private host evidence and is not copied into
Git.

The selected `-b` root passed the following live checks:

| Item | Result |
| --- | --- |
| Run ID | `q04-7b4f958ff3ac4e2da5b54dcaa66914b9` |
| Prefix | `q04/keynote-18be1b3-20260916-b/` |
| Bundle/config SHA-256 | `b729891aa381ae25eef6ec2fbceefcdb43703d441762eafbb388627792833297` |
| Frozen state SHA-256 | `6f83b29e73357e6576643948f18f0be2d461ae7285e433f2c810c5f8d4aca5b7` |
| Python/platform | 3.12.13 / `Linux-6.12.76-linuxkit-aarch64-with-glibc2.41` |
| Packages | 112 installed; zero differences |
| Models | 17 artifacts; zero differences |
| Restored producer | zero differences at `/tmp/q04-keynote-18be1b3-20260916-b/code/src/pdf_processing` |
| Frozen profile | method and five-page grouping match the restored bundle |
| Existing Keynote phase | complete |

The container's `/app/pdf_processing` mount still differs from the frozen
producer and is not selected. `/tmp/q03-20260916-d` was not restored, so the new
probe names the restored Q04 producer and `inputs/inputs.json` explicitly. The old
probe defaults remain available for historical callers. The new runner pins the
complete bundle and state hashes above rather than accepting a new startup hash.

## Reservation and service state

Three restored reservation records are historical evidence only:

| Record | Recorded PID | Live | Lock held | Release marker |
| --- | ---: | --- | --- | --- |
| `reservation.json` | 9913 | no | no | present |
| `reservation-acl-window-3.json` | 10461 | no | no | present |
| `reservation-acl-window-v2-a.json` | 10596 | no | no | present |

The shared remote qualification lock file was absent. All v3 capacity,
reservation, release, sample, verdict, runner, phase and log paths were absent.
The future runner creates a fresh reservation token and holder PID/start-ticks/
lock-inode tuple; no restored PID or record is accepted as live ownership.

All three kind nodes were Ready. T09a Temporal was healthy with no Running
workflow, and object readiness returned 200. All 32 historical Deployment UIDs
matched the approved inventory and every Deployment remained at `replicas=0`,
`ready=0`.

## Private evidence boundary

Sanitized details and hashes are in `evidence/summary.json`. Raw Kubernetes and
runtime probes remain under `/private/tmp` and the restart archive remains under
`/Users/david/work/data-ingestion/.scratch/q04-pre-docker-restart-20260917`.
They contain environment details and are not committed. A later restart, container
replacement, OOM increment or path collision invalidates this baseline and stops
the prepared runner before admission.
