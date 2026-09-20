# K verification

Before K, J raw replay reproduces 54 incomplete attribution samples. A 35-second
no-inference probe reproduces 61 runc PermissionError reads matching J's exact
command hash, errno 13 and smaps_rollup path. A second probe with a prestarted
command lane and the same 50 logical commands has zero read errors. Both temporary
Pods were removed; no workflow, fixture, PVC or threshold was changed.

Local real-subprocess tests cover repeated commands in one PID, isolated request
scope, explicit remote exceptions, a 6MB response, timeout without reconnect and
EOF/close reaping. The existing J transport/stop/preflight/projection/cleanup tests
are exercised against K, including the sample-before-guard path on its new lane.

120 tests passed after regenerating the exact runner/source manifests, including
full argv, isolated source projection and runtime contract, both real process
channel behavior and existing complete failure cleanup. The first full run caught
the intentionally stale runner digest after the last edit; it was regenerated
before review. No runtime had started.
