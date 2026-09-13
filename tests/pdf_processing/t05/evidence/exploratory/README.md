These initial-revision short native cases established SIGSTOP/no-progress and
SIGKILL/crash retry behavior. They are not substituted for final-code acceptance.
The initial 3-page forced-Pod-delete case finished on attempt 1 and is excluded as
proof of recovery. The corrected final controller uses 51 pages and kills group 2.
A separate qualified-v2 run deliberately retained the 8 s fault-only no-progress
setting and timed out a legitimate table stage after 5 pages. The final qualified-v3
run uses the default 180 s allowance and passes full native fidelity. This is evidence
that short spike deadlines are not production calibration; no new SLA is claimed.
Raw sources/registrations for all three prefixes remain in the isolated t05 bucket.

Supervision diagnostics are carried in in-flight Temporal heartbeats and successful
operation summaries. Failure category/code are retained by the Workflow summary;
this slice does not create a public request-status database or copy all heartbeat
history into a separate store.
