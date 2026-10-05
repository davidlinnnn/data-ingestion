# RA2 group-5 native recovery passed

Identity: `t09b-calibration-20260930-ra2`; source `2b6c83d`, one controlled
execution, no automatic retry. All 11 pre-inference gates passed.

Native51 completed with all seven required component OCR results, exact complete
document/checks equality and Temporal business completion. Two groups covering
pages 1–10 remained registered; only pages 11–15 ran at attempt 2. Old worker
parser/scratch cleanup and replacement generation 2 were verified.

Measured loss-to-business-completion interval: **112.7156–112.7365 seconds**,
bounded by the actual SIGSTOP request and observed stopped state. Drain-request
to completion was 112.7846 seconds. This is one recovery case, not a distribution.

Both worker ledgers reconciled: 3,108 client calls / 3,108 server attempts,
149,278,025 B server HTTP RX and 1,614,996,847 B TX. No missing ledgers, unknown
PUT sizes, incomplete calls or SDK retries. Application read amplification
10.5981, largest read chunk 22,539,322 B and concurrent publication inputs
70,573,839 B; these are not total native/retained buffering peaks.

At quiescence: 148,681,815 B unique registered payload, 177,937,087 B total
current prefix, 303 objects / 25 registrations / 271 registered artifacts,
zero orphan attempt objects. Metadata was listed without rehashing payloads
already checked by the runtime consumer; versions are excluded, no retention
action performed, and this is not a snapshot guarantee.

Whole-Pod sampled peak 2,497,429,504 B; minimum VM available 3,164,229,632 B;
largest sample gap 0.4461 s. No Pod/VM OOM. Object full PSI avg10 remained 0.00,
cumulative full PSI increased 21,348 us, memory.events.max increased 4 (recorded
under the existing approved policy). No guard or resource threshold changed.

Status **PASS_DIAGNOSTIC_ONLY**. Runtime cleanup completed, all 32 held Deployments
restored off with no owned Pods/restoration errors, object identity/configuration
unchanged. Evidence PVC `t09b-calibration-ra2-evidence-20260930` remains Bound
(UID `b072b6f2-1e4e-46ec-9990-6be6ed45488a`); raw evidence and prefix retained.
The matched group-10 recovery cell and remaining #45 coverage are still pending.
