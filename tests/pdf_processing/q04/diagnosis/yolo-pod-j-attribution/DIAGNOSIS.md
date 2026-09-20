# J process attribution — reproduced runc observer effect

J's unchanged strict classifier replay yields 54/1,023 incomplete samples, all
unclassified. These remain historical FAIL; no PSS is fabricated.

Ranked hypotheses before intervention: repeated exec helpers; persistent process
permission restriction; workload lifecycle races. A bounded 35-second diagnostic
Pod used the same existing image, node and non-root UID 1000, no PVC, inference,
workflow or producer change. Fifty `/bin/true` execs ran between quiet periods.
The 20ms diagnostic observer captured 61 PermissionError rows and one proc exit
race. Every denied row names `runc:[2:INIT]`, UID/GID 0, errno 13, smaps_rollup,
command hash d1750f4987f0f1657c272aa5bad1b18d9f13b8ef307c789460b006ee2fdb9fe3:
exactly the hash in all 35 J PermissionError process rows. This proves the observed
read-denial class is a container-runtime exec initialization process, rather than
a failed PDF Activity. It does not reconstruct J's missing process PSS or prove
all J process-set races have the same origin.

The controlled counterpart establishes one persistent Python command channel
before starting the same observer. Fifty commands reuse that channel; the same
35-second observation records zero errors. Both Pods had a 120s deadline, no
service-account mount and 256MiB limit; both were removed with UID preconditions.
Before/after Temporal/object health and exact 32 held Deployment UIDs passed.

Minimal repair: prestart independent VM-sample and evidence command lanes before
workload/collector startup. Use existing read programs and existing timing/identity
checks. Keep both processes in the measured cgroup and retain their PSS overhead.
A channel failure is fatal; no reconnect or runtime retry. Process completeness,
confirmed-exit classification, peak rule, PSI/OOM/memory/deadline limits remain
unchanged. K must demonstrate this on the real workload; normal workload birth or
exit races may still fail the unchanged contract and are not preemptively excused.

Evidence: probe-result.json, exec-events.json and persistent/ equivalents; scripts
are retained as diagnostic tools, not automatic acceptance runs. No credentials
or raw command lines are captured. J records remain byte-for-byte unchanged.
