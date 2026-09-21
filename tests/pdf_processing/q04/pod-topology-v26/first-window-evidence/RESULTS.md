# AA runtime result

AA (`q04-warm-pod-cgroup-20260921-aa`) ran once from commit `019fc15` with no automatic retry. All 11 pre-inference gates passed. All five Temporal executions completed, every result had `processing_complete=true`, the sequence issued 29 group requests, and the request-20 parser recycle changed PID 131 to PID 1836.

The combined warm/resource gate did not pass. Four transient process exits were classified, but sample 1291 remained unclassified. Its first observation records fresh child PID 3053 leaving the cgroup membership set; its conservative retry is complete, stable, and confirms that exact identity absent. The next complete sample records the same `(pid,start_ticks)` exit. Because the retry's cgroup memory reading was lower, the collector correctly retained the higher first reading; the classifier lacked this exact complete-retry membership-exit shape. PSS remains unknown and is not substituted.

Node and cgroup full PSI stayed at 0.00, OOM counters stayed zero, available memory never fell below 5,155,491,840 bytes, and the observed outer cgroup maximum was 2,547,748,864 bytes. No threshold change is supported or needed for the next run.

Cleanup passed. The owned Deployment, Pod and ConfigMaps are absent; evidence PVC `q04-pod-cgroup-aa-evidence-20260921-aa` remains Bound with UID `b297d64e-50d9-40fb-ab39-301ab21826a4`; all 32 held Deployments remain exact and off. AA does not prove the combined warm/resource acceptance row.
