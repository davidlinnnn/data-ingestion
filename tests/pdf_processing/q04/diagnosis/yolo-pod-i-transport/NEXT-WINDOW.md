# Remaining I transport blocker / next-window proposal

No second runtime was attempted. Preserve executed I source at commit 41a8816,
all original controller evidence and separately recovered sealed PVC evidence.

The deterministic reproducer executes the real snapshot and mirror. A temporary
worker scratch file is observed in pull 1, removed by normal group cleanup, and
pull 2 raises `remote evidence disappeared`. A separate 11-second cleanup delay
raises `evidence transport gap exceeded`. No network, cluster or timing jitter
is required. This rules out a necessary API outage or Pod identity change as
causes of these two errors.

Before another newly identified window, make this minimal acceptance-tool repair:

1. Define only the recognized `state/<phase>/worker-N/scratch/` subtree as
   transient parser workspace, not durable evidence. Exclude it consistently
   from the authoritative live snapshot/inventory. Keep all durable records,
   worker samples/logs, lifecycle events and required outputs under strict
   missing/truncated/hash checks. Keep I's already captured transient files in
   its original partial mirror; do not purge historical data.
2. Separate failed-window forensic export from continuous live qualification.
   The live 5s transport gap remains a failure. After confirmed owned stop and
   cleanup, use a fresh read-only sealed-inventory export/readback under the
   existing cleanup deadline. Never reset a live mirror gap to manufacture PASS;
   record live failure and successful forensic recovery separately. Retain PVC
   if either export or verification fails. I's manual read-only recovery proves
   the existing PVC/terminal contract can support this path without a new backend.
3. Regression: real snapshot pulls before/during/after scratch creation/deletion;
   durable-file deletion/truncation still fails; interrupted supervisor seals;
   >5s live loss remains failed while post-stop terminal export recovers the
   exact inventory. Exercise controller cleanup end-to-end, including archive
   fingerprint and retained PVC behavior. Project and validate the full CLI/source
   contract, then independent review before execution.
4. Use a new identity/prefix/PVC and unchanged image/producer/oracle/budgets.
   Reconfirm the 32 held UIDs and capacity admission. At most one explicitly
   coordinated window, no automatic retry. No evidence currently justifies
   increased memory, relaxed PSI or replacement of kind.

This is a concrete follow-up proposal, not an activated runner or a change to
acceptance criteria. Main can integrate the current two repairs and diagnosis
while keeping #51 open; runtime readiness remains blocked on this transport fix.
