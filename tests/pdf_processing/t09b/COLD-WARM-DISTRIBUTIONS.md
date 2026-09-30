# Selected group-5 process-cold and normal workflow observations

Descriptive n=3 workflow observations, full required OCR; process-cold means fresh parser first request, host/storage cache uncontrolled. Normal mixed-sequence native crosses the accepted recycle boundary and is not wholly warm. No p95, SLA, confidence or causal cold penalty claim. Durations exclude worker startup and external verifier cost.

| Fixture | Process-cold median / range (s) | Later-request median / range (s) |
| --- | ---: | ---: |
| 06 | 68.155 / 67.981–68.762 | 62.031 / 62.011–65.996 |
| 07 | 39.401 / 36.474–44.006 | 32.964 / 32.669–34.080 |
| 08 | 32.216 / 31.770–33.876 | 27.669 / 27.449–28.367 |
| native | 103.722 / 101.541–104.252 | 111.613 / 110.571–115.038 (recycle mixed) |

Cold cells PC1B/PC2/PC3 rotate the three missing fixture orders; Wiki06 uses
the first request of existing A6/A7/A11. Failed PC1 is retained and excluded.
All successful cells preserve full document/checks, required OCR, complete
storage/HTTP traffic, resource telemetry and owned cleanup.

Cold cell stage-cost.json separates measured child converter wall and Store.publish
wall (upload, registration, integrity readback). Parser internal stage sums are
not wall time; publication is nested within inclusive Temporal activity durations.
The exports use existing metrics/ledgers, no new inference or payload rehash.

These observations support reporting the measured selected workload, not a new
admission bound or production capacity. Group5/one active parser remains selected.
Remaining work: retained/native buffering boundary, conditional concurrency
resolution and consolidated final supported bounds. #45 remains open.
