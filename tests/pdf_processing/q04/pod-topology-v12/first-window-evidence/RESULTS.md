# M — bounded fixture-07 acceptance PASS

Execution commit `d1701d3`, identity `q04-yolo-pod-cgroup-20260920-m`, new prefix
`q04/yolo-pod-cgroup-20260920-m/`. One attempt, no automatic retry.

All 11 pre-inference gates passed. Fresh/restored/exact replay each completed
15/15 pages and all four selected OCR components. Full graph passed the approved
two-pair source-reviewed equivalence. Exact replay retained the fresh request;
restored used a new request and checked existing group/assembly artifacts.
Three fresh groups used three sequential parser identities with max_requests=1.
The candidate fresh index and phase-complete record were promoted only after
the complete resource gate passed.

All 1021 process/cgroup samples were complete, no classified missing-read
exceptions, max gap0.366236417s, sampled peak1,718,480,896 bytes, no PSI/OOM/memory
violations and both final cleanup markers. Outer982 samples had maxgap0.446723s,
minimum node MemAvailable6,373,584,896 bytes, max cgroup1,696,768,000 bytes.
Both observer channels and full archive transport succeeded. Independent
verification matched82 inventory entries, exact membership and83 tar files.

All owned runtime removed with UID fences,32 held Deployment UIDs still at zero,
all prior PVC UIDs retained and Temporal idle. M PVC
`d05b3a16-7431-49d0-88a5-a754be6d4af5` remains. Terminal cgroup and post-cleanup
VM OOM proofs passed. Raw graph payloads and full tar remain at the retained
local root and PVC; RAW-EVIDENCE-MANIFEST.json binds their sizes and SHA256.

M changed only workload-tree THP policy plus diagnostic counters from L. Its
cgroup direct reclaim stayed0; node global counters still changed, including
128 direct scan pages and2 allocstall_movable increments. This pass supports the
chosen bounded runtime but does not prove L's causal mechanism or rule out other
node activity. No global THP, guard, memory capacity or cluster change was made.

This proves fixture07 only under its approved max_requests=1 and equivalence
policy. It does not qualify other fixtures, original request20 warm behavior,
telemetry-loss, process/Pod drain or integrated supported bounds. #51 stays open.
