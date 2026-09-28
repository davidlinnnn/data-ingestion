# Next step after the bounded thread fix

Production OCR now passes the supported ONNX intra-op bound4 directly. CY/CZ are
historical diagnostics whose source manifests intentionally retain the earlier
producer; do not update or rerun them against the changed source. No full matrix
was executed in this turn.

1. Create one fresh producer/input binding for the OCR-only source change, keeping
   fixtures,models,continuation,profiles and exact graph/crop oracles unchanged.
   Explicitly document this one producer difference; no generic source-normalizing
   or oracle regeneration rule.
2. Reuse the full mixed-window runner with a new identity, no diagnostic early-stop
   hook and no runtime constructor override. Preserve CS's user-approved object
   policy and all VM/worker/OOM/deadline/telemetry guards; test projected imports
   and scope, review, then one attempt with fail-stop/no automatic retry.
3. Require all five full document/check graphs,29groups,request20 recycle and
   post-recycle completion, plus terminal business success and complete cleanup.
   A failure stops the window and remains evidence. Do not raise memory or PSI
   thresholds to obtain a pass. Original zero-event qualification remains separate.

Current evidence supports reduced parallel OCR allocator pressure, not universal
zero stalls: CZ still has30 entries/7695us global full PSI and different measured
starting memory. #44 bounds and intermittent reliability remain unqualified;
#45 stays blocked, accepted #51/Q04 history stays closed.
