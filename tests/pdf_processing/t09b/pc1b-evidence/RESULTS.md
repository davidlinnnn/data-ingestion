# PC1B serial process-cold cell passed

Identity t09b-calibration-20260930-pc1b; source 68766d6. One controlled execution,
no automatic retry. Revision follows PC1's diagnosed readiness sampling-lock bug;
failed PC1 is preserved and excluded. Four focused cold tests and 14 projection
tests passed; Standards/Spec review found no remaining blocker. Actual rendered
preflight scope and three-generation final evidence requirements were tested.

All 11 pre-inference gates passed. YOLO07/AIMA08/native51 complete with exact
full document/checks equality, 15/12/51 pages and all 4/9/7 required OCR components.
Temporal business completion, 17 groups, distinct parser PIDs131/282/528 and no
recycle verified. Each fixture starts a fresh worker; previous parser/scratch is
absent before successor launch. The corrected launch transition retains the
1-second gap contract while readiness waits run with sampling active.

| Fixture | Process-cold workflow seconds | Required OCR activities |
| --- | ---: | ---: |
| YOLO07 | 36.4737 | 4 |
| AIMA08 | 31.7702 | 9 |
| native51 | 101.5409 | 7 |

These are first-request workflow times, including required work, not worker
startup-plus-verification total or fully cold host/storage observations. Each
fixture has n=1 here; PC2/PC3 remain planned. Temporal activity times include
storage/publication, not exclusive stage timers.

All three ledgers reconciled: 5,405 client calls/server attempts, HTTP RX
221,504,990 B / TX2,304,156,845 B. No missing ledgers or trace losses. Whole-Pod
sampled peak 2,550,530,048 B, minimum VM available 2,895,884,288 B, max gap0.3903s.
No OOM; object full avg10 remained0, max events delta0, full PSI delta19,637us.
Same approved diagnostic policy, resources and thresholds.

Quiescent inventory: registered payload220,469,389 B, total current prefix
250,999,716 B, 525 objects/58 registrations/458 artifacts, no orphan attempts.
Metadata only, no payload rehash, versions/retention excluded, no snapshot claim.

PASS_DIAGNOSTIC_ONLY; runtime cleaned, all32 held Deployments restored off,
no owned Pods/restoration errors, object identity/config unchanged. Evidence PVC
`t09b-calibration-pc1b-evidence-20260930` remains Bound with UID
`e7338a9f-d6e5-4545-8112-b55f464fcb4a`; raw evidence/prefix retained.

#45 stays open: two cold replicates, total buffering/exclusive stage attribution,
conditional concurrency resolution and final supported bounds remain pending.
