# AB runtime result

AB (`q04-warm-pod-cgroup-20260921-ab`) ran once from commit `d58118b` with no automatic retry. All 11 pre-inference gates passed. All five Temporal executions completed with `processing_complete=true`; the sequence processed 28, 15, 12, 51 and 28 pages, issued 29 group requests, and recycled the parser from PID 131 to PID 1836 at request 20.

The combined warm/resource gate did not pass. Sample 691 was the only raw incomplete process sample. The reviewed classifier safely marked it `classified_confirmed_exit` for fresh child identity `(1753, 19040994)`, and the summary recorded no unclassified cgroup transition. The exited child's PSS is still unknown, so the executed summary correctly retained `process_attribution_complete=false` under the adopted measurement contract. The workload exited 1 after all business work completed.

Node and cgroup full PSI stayed at 0.00, VM and cgroup OOM counters stayed zero, available memory never fell below 5,161,975,808 bytes, and the observed outer and inner cgroup maxima were 2,601,865,216 and 2,637,160,448 bytes. No threshold change is supported or needed.

Cleanup passed. The owned Deployment, Pod and ConfigMaps are absent; evidence PVC `q04-pod-cgroup-ab-evidence-20260921-ab` remains Bound with UID `1111fa94-ca48-4a4a-a5ef-c7853f3904e4`; all 32 held Deployments remain exact and off. AB proves cgroup continuity and the successful warm business sequence, but it does not prove complete process attribution or the combined warm/resource row. An unchanged rerun is not warranted; the next proposal must capture a stable complete process sample without discarding the higher cgroup guard observation or redefining unknown PSS as known.
