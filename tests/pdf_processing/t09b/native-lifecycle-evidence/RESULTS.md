# Failed trace lifecycle diagnostic

Two uniquely tagged marker PUTs were observed, but remote stop failed. The object
image lacks awk; startup therefore failed while recording the timeout PID, before
installing its cleanup trap. The already-started timeout/mc survived the local
transport. No PDF workflow or Deployment change occurred.

Targeted process-group cleanup used the observed timeout PID 350/start ticks
48355122 and child mc PID 352. mc was confirmed absent. Timeout 350 remains a
zero-address-space zombie adopted by PID 1; no running trace remains. The object
Pod was not restarted to remove it. This diagnostic is FAILED, not cleanly passed.

The corrected implementation uses shell positional fields instead of awk and
installs its trap before reading PID metadata. A separate fresh-prefix diagnostic
in native-lifecycle-corrected-evidence proves observed markers and remote stop.
