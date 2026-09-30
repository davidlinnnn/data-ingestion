# PC1 stopped: readiness wait incorrectly blocked sampling

Source 7a89111; identity t09b-calibration-20260930-pc1. All 11 gates passed;
YOLO07 reached successful 15-page business completion. The next worker launch
failed qualification before AIMA/native workflows ran. Do not count this as a
complete cold replicate or a production ingestion failure.

Traceback points to cold_trials wrapping host.start (launch plus readiness wait)
in collector.process_transition. This holds its sampling lock for the operation:
1.009470 seconds, producing an observed 1.021253-second sample gap. Both violate
the unchanged 1-second attribution contract. Shutdown itself took 0.258550s.
No OOM/capacity/deadline stop is established by this failure. Other potential
causes of startup duration are not needed to establish the incorrect lock scope.

Regression uses the real StrictAttributionCollector.process_transition and
T09b Host.start with a deterministic 1.009470-second readiness delay. It reproduced
the exact RuntimeError before correction and passes after using existing
prepare_start / launch_start / await_ready methods: only launch is sampling-locked,
readiness is observed with sampling active. No gap threshold is increased.

Failed runtime cleaned, both workers stopped with parser/scratch absent, all32
held Deployments off, no owned Pods/restoration errors, object service unchanged.
PVC/prefix and raw failure-evidence archive retained. No automatic retry.
