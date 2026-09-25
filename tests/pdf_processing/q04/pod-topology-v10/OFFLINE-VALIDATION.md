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

Initial suite ran 120 tests; review follow-up found the copied transport suite's
default still selected J. It is now explicitly K, with a red/green regression
showing channel-close failure cannot suppress second-lane or owned-runtime
cleanup. Final rerun uses both Q04_RUNNER_VERSION=k and Q04_TRANSPORT_VERSION=k.
The generated manifest is refreshed after these reviewed changes.
