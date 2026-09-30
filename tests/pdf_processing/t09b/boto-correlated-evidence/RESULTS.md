# Correlated boto3 accounting probe

Four SDK calls (16-byte and 4096-byte PUT/GET) matched four native MinIO
HTTP records by X-T09b-Call-Id. Exact readback passed. The durable ledger
is complete; observed SDK retries were zero. Server counters total 4878
received bytes and 4112 sent bytes. These are HTTP accounting counters,
not packet-level wire bytes. The correlation header itself adds overhead.

Objects remain under the unique prefix recorded in result.json. The local
port-forward stopped; the bounded trace exited 124 at its expected timeout.
No PDF workflow, Deployment change, or performance baseline was executed.

Local SDK fault tests separately cover a retry retaining the same call ID and
a truncated response. Runtime trace lifecycle and complete workflow export
remain required before baseline admission.
