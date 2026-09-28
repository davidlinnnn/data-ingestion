Q04 warm runtime U (`q04-warm-pod-cgroup-20260921-u`) ran once without retry.
The complete fixed sequence Wiki06 → YOLO07 → AIMA08 → native → Wiki06 finished
all 29 group requests. Parser PID 131 served requests 1–20, then recycled once to
PID 1836 for requests 21–29. All five Temporal workflows completed. Wiki/native
pending graph records remained explicitly measurement-only and were not promoted
to fixture acceptance.

Resource qualification failed closed on one of 1,438 process-attribution samples.
Sample 1065 caught a normal short-lived child exit while `/proc` identity was
being enumerated: the child was complete immediately before, produced one matching
exit event, was absent from both current inventories, and the following sample was
complete. Its PSS remains unknown, so U does not satisfy complete process
attribution. The incomplete sample was not the peak.

Maximum cgroup memory was 2,530,975,744 bytes, minimum available node memory was
5,278,797,824 bytes, and full PSI/OOM remained zero. No resource threshold or
deadline fired. Cleanup completed with UID-fenced removal of owned runtime; the U
evidence PVC is retained Bound and all 32 held Deployments remain exact and off.

V adds one bounded immediate re-enumeration only for a PID that disappears with
`FileNotFoundError`/`ProcessLookupError`. Persistent errors, permissions, changing
inventories and incomplete peak attribution remain fail-closed. Thresholds are
unchanged. #51 remains open pending complete process attribution and the other
unproven matrix rows.
