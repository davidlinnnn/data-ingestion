# Q04 AU active telemetry-loss gate

Run one native fixture workflow using the frozen AH producer and existing resource limits. After five registered pages, the controller stops only the worker's sampler while the next parser group is active. The expected result is a detected telemetry gap, owned workflow cancellation, absent complete registration, and verified worker/Pod cleanup. The independent attribution collector and host observer remain active throughout.

AU uses a new identity and object prefix after AT proved the guard but exposed a verifier error: Temporal marked the workflow execution `COMPLETED` while its business result was failed. AU decodes the terminal payload and rejects only a successful business completion. All earlier evidence remains intact, and this run has no automatic retry. A guard failure proves only this negative gate; it does not satisfy process or Pod drain recovery or the operating-bounds report.
