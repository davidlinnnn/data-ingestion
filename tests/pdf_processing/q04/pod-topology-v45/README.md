# Q04 AT active telemetry-loss gate

Run one native fixture workflow using the frozen AH producer and existing resource limits. After five registered pages, the controller stops only the worker's sampler while the next parser group is active. The expected result is a detected telemetry gap, owned workflow cancellation, absent complete registration, and verified worker/Pod cleanup. The independent attribution collector and host observer remain active throughout.

This run has a new identity and object prefix, preserves all earlier evidence, and has no automatic retry. A guard failure proves only this negative gate; it does not satisfy process or Pod drain recovery or the operating-bounds report.
