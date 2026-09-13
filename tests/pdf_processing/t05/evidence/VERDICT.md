# T05 bounded native warm-worker qualification

Implementation: `c7844af`, based on accepted T02 `e09f23e`. The mounted producer
hashes are recorded in `runtime.json`. Mandatory two-axis code review is pending;
this report is not ticket closure or a production-wide readiness claim.

## Passed real-service observations

- One warm parser processed the three-page native review source and the 51-page
  paper. The paper retains historical full Docling JSON SHA256
  `fd45828175ad659df5b25d90a6c463adc43ddc8c813737d98e1ae6f583d71aab`.
  The second source also matches the retained T02 fresh-interpreter document JSON
  exactly (`43b15d1f2695954368cd920c9c5ea84d4da16f851879e66f680edfffa2350576`).
- All 9 invalid submission/source cases failed explicitly before registered page work.
- Actual idle Pod replacement reused all 14 operations across both sources with zero
  uploaded bytes. Assembly remained fresh-process, with no repeated page inference.
- Forced Pod loss during group 2 of the 51-page source retained the first 5 registered
  pages. Group2 retried on attempt 2, remaining groups completed, and output matched
  the normal baseline. Worker identities changed in Temporal history.
- Graceful Pod deletion during native work let the active group finish/register;
  remaining groups moved to the replacement worker. Every Activity stayed attempt 1
  and the final full document matched.
- A real native child with test-only TERM resistance was stopped externally. The
  local 8 s diagnostic no-progress allowance expired, TERM was resisted, the child
  exited by SIGKILL, and attempt 2 succeeded. The retained prior exit code is -9;
  the new child has a different PID. This is not evidence of an actual kernel OOM.
- Three externally killed native attempts produced a terminal parser failure at
  maximum attempt 3, rather than an unlimited restart loop.
- During a test-only 8 s pause immediately before real object-store publication,
  graceful Pod deletion allowed the group to register and complete on attempt 1.
  Assembly finished on a replacement worker and output matched the baseline.
- Activity scratch was empty after completion. The isolated module tests also
  check TERM-resistant reap, request correlation/method mismatch, hard deadline
  despite continuing progress, and cancellation before scratch cleanup.

- The unchanged two-page scanned fresh baseline/capture/restore regression passed
  in the pinned Linux runtime (32.8 s), with full JSON equality and zero repeated
  page inference during restoration. This is regression coverage, not warm scanned
  profile qualification.

## Limits and evidence handling

The initial too-fast 3-page Pod deletion is not claimed as recovery evidence.
A controller-selected terminating Pod made the first publication-drain injection
invalid; `pubdrain-2` is the accepted run. Those unqualified runs remain distinct.
The8s fault-only budget also failed a legitimate full-paper table stage; final
normal/Pod/drain runs used the default 180 s provisional no-progress allowance.

The native process-start count includes initial spawn; memory is process peak RSS,
not whole-Pod or sustained growth qualification. No actual kernel OOM or storage-node
failure was manufactured. Repeated SIGKILL verifies the abrupt-resource-failure
retry path, not a memory-capacity limit. Cross-profile/sustained qualification and
numeric deployment calibration remain T09a/T09b. Current 3 s / 8 s test allowances are
not adopted deployment settings. The deployable defaults remain provisional.

Raw source versions, attempt payloads and registrations remain in the isolated
`pdf-t05-validation` MinIO PVC / `t05` bucket. Prefixes `qualified`, `qualified-v2`
and `qualified-v3` separate initial, short-budget and final-code evidence. No old
validation namespace/PVC was removed. No shared artifact GC, canonical completion,
HTTP admission or public request-status database was introduced.
