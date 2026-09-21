# Z runtime result

Z (`q04-warm-pod-cgroup-20260921-z`) ran once from commit `f83d1db` with no automatic retry. Ten of eleven pre-inference gates passed. The `workload_imports` gate failed with `ValueError: runtime scope digest changed`, so no workflow, inference, Temporal execution, or object write started.

The runtime integration manifest declared the outer runner authorization digest (`eb940293…`) where the candidate validates the canonical digest of its narrower measurement scope (`d9087af3…`). The local projected-workspace regression imported the modules and exercised the reference checker but did not call `verify_workload_imports_z`, so it did not catch this exact pre-inference failure.

This is an acceptance packaging defect. It provides no new evidence about ingestion correctness, process attribution, PSI, OOM, memory floors, or deadlines. Those runtime properties remain at Y's evidence state.

Cleanup passed. The owned Deployment, Pod, and ConfigMaps are absent; evidence PVC `q04-pod-cgroup-z-evidence-20260921-z` remains Bound with UID `f137ee66-338f-479a-83e0-198971577840`; all 32 held Deployments remain exact and off. Z does not prove the combined warm/resource acceptance row.
