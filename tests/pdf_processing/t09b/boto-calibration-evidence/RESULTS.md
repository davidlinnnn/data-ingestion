# Boto3 conditional PUT / GET calibration

The fresh 16-byte and 4096-byte objects were uploaded with put_object and
IfNoneMatch='*', then read back exactly. Four complete client ledger operations
match four scoped server trace records; no SDK retry occurred. No PDF workload.

GET tx was 16 and 4096 bytes. PUT rx was 218 and 4298 bytes: payload plus 202
in these two observations, not a universal fixed-overhead rule. The MinIO counters
are kept separately from client-delivered/submitted bytes. Credentials were read
in memory from the existing access Secret and never printed or written.

Temporary port-forward ended, trace ended at its 20-second limit; cleanup.json
records both exits. Both fresh objects are retained. This proves the successful
client path for this fixture, not coverage of dropped trace events or failed
network attempts. Complete benchmark observation still requires trace/client
reconciliation for every operation and explicit failure on missing observations.
