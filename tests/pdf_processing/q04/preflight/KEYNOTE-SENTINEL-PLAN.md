# Q04 process-mode Keynote sentinel — proposed, not authorized

Base runtime: `18be1b3fbcb929921ec986a1a0bf93e4be995b4d`. No runtime code is changed
by this preflight. Main must approve scope, capacity owner, the current time window,
and any service pauses before the commands below are used. **None were executed.**

## Bounded work and gates

Run `matrix --fixture 10` only: three Keynote workflows (fresh, restored new request,
exact replay), each on a newly owned worker process and unique queues. The fixed
one-page PDF is SHA-256 `b9919f9684bc6fdfda2f8ead641607e8cb4c10c2abd7842db2d96ec8579d1d9e`.
The reference has 41 texts, one picture and zero tables; 27 reviewed Keynote regions
must pass along with the complete graph. Fresh and restored requests must each
register the selected picture OCR; replay must reuse every recorded step and the
exact final identity. Required evidence and relationships remain publication gates.

`init` captures **all six original sources** and freezes eight profile queues because
that is the existing adapter contract. It performs no inference. The subsequent
matrix processes only fixture 10. No warm, drain, guard, other-fixture or invalidation
workflow is in this sentinel scope. A PASS qualifies only this bounded sentinel.

Proposed 20-minute lease: no new work after minute 15; final five minutes reserved
for cancellation, worker cleanup, evidence collection and restoration checks.
`capacity.draft.json` contains reviewable thresholds and deliberately invalid null
owner/approval/timestamps. It is not an executable approval.

| Guard | Proposed value |
|---|---|
| Continuous admission before each of three cases | 60 s, MemAvailable ≥ 3 GiB (3,221,225,472 B), full PSI avg10=0 |
| Active VM floor | 1.5 GiB (1,610,612,736 B) |
| Coordinator cgroup sampled ceiling | 3 GiB (includes all processes/cache charged to this Pod) |
| OOM | No increase from each fresh baseline; VM counter stays fixed across workers |
| Full PSI / sample gap | 0 / at most 3 s |
| Each workflow execution timeout | 180 s, further clipped to remaining work window |
| Init outer bound | INT at 60 s, KILL after another 15 s |
| Matrix outer bound | INT at 825 s, KILL after another 180 s |
| Cleanup reserve / replacement field | 300 s / 90 s (replacement unused here) |

These are proposed conservative experiment stop rules, not supported resource
sizing. The cgroup ceiling is sampled, not a kernel hard limit. The observed
2.26–2.31 GiB available **does not meet admission**. Request a fresh lease for the
20 exact candidates in [PAUSE-CANDIDATES.md](PAUSE-CANDIDATES.md), or wait for sufficient
capacity. Recheck afterward; do not lower bounds or widen the pause set automatically.
If a deadline kills the controller before cleanup is proven, the result is failed
with cleanup pending, never a successful hard bound on every orphan process.

## Immutable placement and prerequisites

- Local private package: `/private/tmp/q04-keynote-18be1b3-20260916-a-package`.
  `repo.tar` is a Git archive of exactly the base commit's `src` and `tests/pdf_processing`.
  `inputs.tar` is verified private bundle v5; archive hashes are in `evidence/package.json`.
- Remote root: `/tmp/q04-keynote-18be1b3-20260916-a` in namespace
  `pdf-t09a-validation`, Pod `coordinator`, UID `39c4bf45-45ae-4646-8d7b-ec47b2c61785`.
  Use `code`, `inputs`, `state`, `logs`, `capacity.json` beneath that root.
- Object endpoint `http://objects:9000`, bucket `t09a`, new prefix
  `q04/keynote-18be1b3-20260916-a/`. Both prefix and root were unused at preflight.
- Python `/experiment/.venv/bin/python`; model cache `/experiment/PROTOTYPE-wipe-me/hf`.
  Use the staged code via explicit PYTHONPATH; **never `/app/pdf_processing`**.
- Main supplies a current approved capacity JSON at
  `/private/tmp/q04-keynote-18be1b3-20260916-a-package/approved-capacity.json`.
  Copy the proposed numerical fields, fill actual owner/reference and a 1200-second
  starts_at/ends_at window. A nonempty string is only the harness's mechanical check;
  actual main approval is still required. No such file was created in this phase.
- Reserve the shared coordinator qualification lock for the whole init/matrix/cleanup
  interval through the capacity owner. The driver itself locks each CLI invocation;
  the lease must prevent unrelated runs in the gap. No other inference may share
  the coordinator. Recheck current UID, fingerprints, idle state and available memory.
- The coordinator `/tmp` is a writable container layer, **not a PVC**. Keep this Pod
  intact and export artifacts before releasing the lease. Versioned object and
  Temporal state are on existing bound PVCs, which are never deleted.

## Exact staging commands, after main approval

Run on the local host. A conflicting path is an error, not permission to erase or
reuse it. If any stage/init fails, retain its directory/prefix and assign a new run
identity for a later attempt. Do not overwrite an old result or reinterpret a request.

```sh
set -eu
Q04_PACKAGE=/private/tmp/q04-keynote-18be1b3-20260916-a-package
Q04_ROOT=/tmp/q04-keynote-18be1b3-20260916-a
Q04_NS=pdf-t09a-validation
test "$(kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" get pod coordinator -o jsonpath='{.metadata.uid}')" = 39c4bf45-45ae-4646-8d7b-ec47b2c61785
test -f "$Q04_PACKAGE/approved-capacity.json"
python3 - <<'PY'
import hashlib,json
from pathlib import Path
root=Path('/private/tmp/q04-keynote-18be1b3-20260916-a-package')
manifest=json.loads((root/'package.json').read_text())
for name,digest in manifest['archives'].items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest
PY
kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" exec coordinator -- mkdir "$Q04_ROOT"
kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" exec coordinator -- mkdir "$Q04_ROOT/code" "$Q04_ROOT/inputs" "$Q04_ROOT/logs"
kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" exec -i coordinator -- tar --keep-old-files --no-same-owner -C "$Q04_ROOT/code" -xf - < "$Q04_PACKAGE/repo.tar"
kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" exec -i coordinator -- tar --keep-old-files --no-same-owner -C "$Q04_ROOT/inputs" -xf - < "$Q04_PACKAGE/inputs.tar"
kubectl --context kind-internal-a2a-vs6-local -n "$Q04_NS" exec -i coordinator -- /experiment/.venv/bin/python -c 'import sys;from pathlib import Path;Path("/tmp/q04-keynote-18be1b3-20260916-a/capacity.json").open("xb").write(sys.stdin.buffer.read())' < "$Q04_PACKAGE/approved-capacity.json"
```

Then verify staged hashes and approved window, and execute. The lock and `x`-mode
artifact writes are part of the unchanged adapter; shell `-C` forbids log replacement.
Run via an attended local terminal; loss of the kubectl connection is a failure
requiring a fresh read-only inspection, not a reason to submit another workflow.

```sh
kubectl --context kind-internal-a2a-vs6-local -n pdf-t09a-validation exec coordinator -- sh -euC -c '
Q04_ROOT=/tmp/q04-keynote-18be1b3-20260916-a
Q04_PY=/experiment/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 OMP_NUM_THREADS=4
export PYTHONPATH="$Q04_ROOT/code/src:$Q04_ROOT/code/tests/pdf_processing/q04:$Q04_ROOT/code/tests/pdf_processing/q02:$Q04_ROOT/code/tests/pdf_processing/q03"
cd "$Q04_ROOT/code"
"$Q04_PY" -c "import json,time;from pathlib import Path;from prepare import verify_bundle;from contracts import validate_window;verify_bundle(Path(\"$Q04_ROOT/inputs\"));validate_window(json.loads(Path(\"$Q04_ROOT/capacity.json\").read_text()),time.time())"
timeout --signal=INT --kill-after=15s 60s "$Q04_PY" tests/pdf_processing/q04/q04_runtime.py --phase init \
  --bundle "$Q04_ROOT/inputs" --state "$Q04_ROOT/state" --capacity "$Q04_ROOT/capacity.json" \
  --temporal temporal:7233 --endpoint http://objects:9000 --bucket t09a \
  --prefix q04/keynote-18be1b3-20260916-a/ --model-cache /experiment/PROTOTYPE-wipe-me/hf \
  --trial-seconds 180 --capacity-approved > "$Q04_ROOT/logs/init.log" 2>&1
timeout --signal=INT --kill-after=180s 825s "$Q04_PY" tests/pdf_processing/q04/q04_runtime.py --phase matrix --fixture 10 \
  --bundle "$Q04_ROOT/inputs" --state "$Q04_ROOT/state" --capacity "$Q04_ROOT/capacity.json" \
  --name keynote-window-1 --trial-seconds 180 --capacity-approved > "$Q04_ROOT/logs/matrix.log" 2>&1
'
```

The Linux timeout runs inside the coordinator; it is not the kubectl transport's
lifetime. Worker readiness is bounded at 90 s; native child/startup budgets remain
those frozen in the adapter. The shorter workflow/window limits govern this sentinel.
No hard failure may trigger an automatic rerun under the same paths or prefix.

## Stop, cleanup and evidence

Normal completion or a guard failure invokes the adapter's owned-workflow cancel /
20-second completion check / terminate fallback, then owned worker SIGTERM and
parser shutdown. It verifies PID creation time and worker command before signaling;
forced cleanup is a qualification failure. Missing parser/scratch proof keeps
ownership pending. Histories, initiating error and each cleanup outcome are separate.

For an operator stop, run the following **only during the subsequently approved
sentinel**, from a second terminal. It sends INT only to the exact sentinel driver;
no service Deployment, arbitrary Python process or unrelated workflow is targeted.

```sh
kubectl --context kind-internal-a2a-vs6-local -n pdf-t09a-validation exec -i coordinator -- /experiment/.venv/bin/python - <<'PY'
import psutil,signal
root='/tmp/q04-keynote-18be1b3-20260916-a'
matches=[]
for p in psutil.process_iter():
    args=p.cmdline()
    if args[:2]==['/experiment/.venv/bin/python','tests/pdf_processing/q04/q04_runtime.py'] and root+'/state' in args and 'keynote-window-1' in args:
        matches.append((p,p.create_time(),args))
assert len(matches)==1, 'inspect retained state; do not guess a PID or resubmit'
p,created,args=matches[0]
assert p.create_time()==created and p.cmdline()==args
p.send_signal(signal.SIGINT)
print('Sent INT to owned driver',p.pid)
PY
```

Observe for at most 180 seconds. Verify each case's `workflow.json` ID is terminal
in Temporal, every `worker-N/ownership.json` PID/create-time no longer runs,
`stopped.json` matches generation/PID and reports parser_absent/scratch_absent, and
`phase-cleanup.json` has no errors. Inspect no remaining parser descendants. A
complete result must have all consumer checks; an interrupted new request must
have no complete registration (`Run.no_complete` scans every page of registrations).
Do not infer clean shutdown from the kubectl exit code alone.

If the controller is gone and cleanup is unresolved, keep the lease in incident
cleanup state: recheck exact workflow IDs and recorded worker identities, cancel /
terminate only those workflows through `Run.cancel_owned`, signal only a still
matching worker and its verified descendants through `Host.signal` / `force_stop`.
An already missing parent with an unidentified orphan is **not** authorization for
`pkill`, broad process-group killing, a Pod delete or service scaling; retain evidence
and resolve that identity with main. This contingency is not automatic qualification
or permission to extend inference beyond the window. No output/PVC/source deletion.

Export raw state/logs to a new private local path even after failure:

```sh
set -eu
set -o pipefail
Q04_CAPTURE=/private/tmp/q04-keynote-18be1b3-20260916-a-results
mkdir "$Q04_CAPTURE"
kubectl --context kind-internal-a2a-vs6-local -n pdf-t09a-validation exec coordinator -- tar -C /tmp/q04-keynote-18be1b3-20260916-a -cf - state logs capacity.json |
  tar --keep-old-files -C "$Q04_CAPTURE" -xf -
```

Hash the capture and retain all partial states. Keep raw PDF/text/image/history
outside Git. Only after cleanup and capture, restore any newly authorized paused
Deployments to the exact recorded replicas/UIDs, verify service readiness and no
running workflows, record OOM counters, and release the lease. If cleanup cannot
finish by the deadline, report the incident immediately; do not mark PASS.
