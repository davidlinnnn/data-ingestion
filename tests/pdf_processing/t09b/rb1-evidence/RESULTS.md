# RB1 group-10 native recovery passed

Identity `t09b-calibration-20260930-rb1`; runtime source `98998cd`.
One controlled execution, no automatic retry. All 11 pre-inference gates passed.
Native51 completed with all seven required component OCR results and exact
complete document/checks equality. One registered group retained pages 1–10;
only pages 11–20 ran at attempt 2. Both worker generations stopped with their
parser and scratch absent.

Actual SIGSTOP request/observed-stop bounds give loss-to-business completion
**116.5663–116.5868 seconds**; drain-request to completion 116.6166 seconds.
This is one measured recovery case, not a distribution.

Traffic reconciled across both worker ledgers: 3,313 client calls/server attempts,
149,011,515 B server HTTP RX and 1,867,302,641 B TX. Application read amplification
12.2779; no missing ledgers, incomplete calls, unknown PUT sizes or SDK retries.
Largest read chunk 22,539,322 B and publication inputs 70,573,839 B are partial
buffer measurements, not total native/retained buffering peaks. Quiescent
checkpoint inventory has not yet been recorded for this cell.

Whole-Pod sampled peak 2,525,315,072 B; minimum VM available 2,845,032,448 B;
largest sample gap 0.3966 s. No Pod/VM OOM. Object full PSI avg10 remained 0.00,
cumulative full PSI increased 15,045 us and memory.events.max increased 6,
recorded under the unchanged approved diagnostic policy.

Status PASS_DIAGNOSTIC_ONLY. Cleanup verified all 32 held Deployments off,
no owned Pods/restoration errors, unchanged object-service identity/configuration.
PVC `t09b-calibration-rb1-evidence-20260930` remains Bound with UID
`22ef47a0-3ec4-4ef0-a1e7-ca2d0141de50`; raw evidence and prefix retained.
