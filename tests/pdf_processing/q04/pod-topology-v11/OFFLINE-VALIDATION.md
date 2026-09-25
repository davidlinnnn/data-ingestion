# L offline validation

K retains the recurring kubelet readiness exec; local inspection identified the
remaining caller and K telemetry again records the exact runc command hash.
The new topology regression first fails on readinessProbe, then passes with the
identical command/period/threshold as startupProbe. Full render validation binds
this exact topology. Existing persistent-channel, interrupted-supervisor, strict
transport, cleanup and source-projection tests are selected explicitly for L.
No attribution rule is changed. Final test counts and reviews are in REVIEW.md.
