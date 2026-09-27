# DB: full mixed window after the shared OCR thread bound

Base 970f28c. One new t09a-bounds-20260928-db identity and prefix.
The only input-bundle delta from CS/CD is producer.ocr.py: supported ONNX intra-op4.
Fixtures, models, profiles, continuation and exact AI/AJ output/check oracles stay unchanged.
No sitecustomize hook, early stop or constructor override. Use production bytes.
Reuse CS functional diagnostic policy: record cumulative object PSI, stop on
positive object avg10, preserve all VM/worker/OOM/floor/deadline/telemetry guards.
Temporarily activate the 32 recorded Deployments, object1Gi and managed low768MiB;
require125s protection admission. One attempt, fail-stop, no automatic retry.
Require five full results [06,07,08,native,06],29groups, request20 recycle,
post-recycle completion and terminal business success. Preserve residual PSI.
Restore32off/object512Mi/health, policy, workers and observers; retain PVC/prefix.
This functional window does not retroactively meet the original zero-event
criterion, establish universal bounds, close#44 or change accepted#51 history.
