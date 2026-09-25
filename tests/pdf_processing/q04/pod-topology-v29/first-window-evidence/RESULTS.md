# Q04 AD warm runtime result

AD ran once as `q04-warm-pod-cgroup-20260922-ad`; it was not retried. All 11 pre-inference gates and all five Temporal workflows completed with `processing_complete=true`, registering 28, 15, 12, 51, and 28 pages. The 29-group sequence and request-20 parser recycle completed.

The new terminal synchronization worked: controlled worker shutdown took 0.6155 s, stayed below the unchanged 1 s gap, and was bracketed by complete process samples while the independent outer controller continued cgroup observation. AD had 1,376 inner samples with maximum gap 0.7807 s. Peak process attribution and cgroup qualification passed. Node and cgroup full PSI were 0.0, OOM counters stayed zero, minimum available memory was 5,164,544,000 bytes, and outer/inner cgroup maxima were 2,480,967,680 / 2,430,500,864 bytes.

The overall result remains **FAIL**. Three fresh-child exits overlapped samples 589, 686, and 1121; the request-20 warm parser recycle overlapped sample 958. Exact exits and adjacent complete samples prove cgroup continuity, but the missing process PSS values remain unknown, so `process_attribution_complete=false`. This is not a terminal cleanup, capacity, PSI, OOM, deadline, Activity, supervisor, or ingestion failure.

Cleanup passed. Owned runtime is absent, all 32 held Deployments remain exact/off, and PVC `q04-pod-cgroup-ad-evidence-20260922-ad` is retained Bound with UID `878fa0d8-83e4-4b4b-bcb4-7223bc38c3f5`.

The next implementation must expose a bounded owned-process lifecycle handshake to the measurement harness for fresh-child exits and warm-parser recycle. It must preserve output semantics, independent cgroup observation, the 1 s gap, and unknown-PSS fail-closed behavior. AD is not a Q04 pass.
