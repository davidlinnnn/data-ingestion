# YOLO attribution-B lifecycle diagnosis

The retained run remains **measurement INCOMPLETE** because its controller
`cancel_requested` marker is absent. Its 379 individual attribution samples are
complete, however, and the Temporal cancellation timestamp is retained as an
independent fact. Those facts are sufficient to decide whether overlap existed
before the initial guard breach. They do not turn the run into an acceptance
pass.

The worker guard reported its first breach at 1789773300.962838 with
`memory.current=4,302,082,048`. The 250 ms stream has no sample at that exact
instant, so the table shows the adjacent synchronized samples. “At breach” means
the first attribution sample after the worker report, 104 ms later.

| Point | Time | `memory.current` | Warm parser PSS | Fresh parse child PSS | Worker PSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| Before assembly marker | 1789773297.448392 | 4,004,401,152 B | 1,723,029,504 B | 0 B | 81,881,088 B |
| Before first guard breach | 1789773300.809416 | 4,286,320,640 B | 1,663,398,912 B | 324,588,544 B | 82,567,168 B |
| At first guard breach | 1789773301.066548 | 4,305,158,144 B | 1,663,398,912 B | 343,577,600 B | 82,567,168 B |
| Before cancellation | 1789773301.066548 | 4,305,158,144 B | 1,663,398,912 B | 343,577,600 B | 82,567,168 B |
| Peak | 1789773303.645834 | 4,581,400,576 B | 1,655,742,464 B | 626,794,496 B | 82,601,984 B |
| Both parser processes exited | 1789773305.712855 | 2,604,711,936 B | 0 B | 0 B | 85,368,832 B |

Assembly was observed at 1789773297.708293. Temporal cancellation was requested
at 1789773301.249849. The fresh parse child and warm parser were therefore both
live in the sample immediately before the guard report, in the first sample over
4 GiB, and in the final sample before cancellation. The post-cancel peak is
higher, but it is not needed to explain the initial breach.

The production path explains the lifetime overlap:

1. Group capture returns while `WarmParser` intentionally keeps its model-loaded
   process idle for reuse.
2. Assembly materializes the groups and calls `Execution.child(...,
   mode="restore")`.
3. Restore always starts a fresh parser process. The old warm process has no
   assembly role, but previously remained alive until recycle, cancellation or
   worker shutdown.
4. Multiple profile queues share one `WarmParser`; per-queue activity limits do
   not by themselves serialize all queues.

The selected fix places the seam in `WarmParser`: an assembly fresh-child
handoff reaps the idle warm parser, then holds the same ownership lock for the
entire fresh-child lifetime. An active capture finishes before handoff, no other
queue can rebuild the warm parser during assembly, and the next capture rebuilds
it afterward. This directly removes the overlap visible before the first breach.

Stopping only after the guard or at cancellation is too late for the initial
breach. Raising the guard is outside the accepted constraints. Model unloading
inside the warm protocol would add a larger state transition and new native
library assumptions without evidence that it is needed.

Machine-readable point selection is in
[`evidence/lifecycle-overlap.json`](evidence/lifecycle-overlap.json). The
analyzer verifies the raw archive against the SHA-256 retained by the original
result, records both the result-summary and archive hashes, and selects points
without rewriting the attribution-B result.
