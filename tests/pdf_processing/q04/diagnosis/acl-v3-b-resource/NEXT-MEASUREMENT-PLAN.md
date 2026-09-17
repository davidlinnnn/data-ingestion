# ACL resource next-step options

No option below is authorized by this document. Every run needs a new phase,
paths/prefix, capacity record and explicit main-session window. Keep v3-a/v3-b
immutable and keep the 32 historical Deployments main-owned and closed.

## Recommended first step: measurement-scope calibration

Add qualification-only telemetry outside the frozen producer. Run **fresh fixture
09 only**; do not spend capacity on restored/replay until a fresh case completes
within an approved envelope.

Capture at 250 ms while the worker is live:

- resolved cgroup-v2 mount, relative path and inode; `memory.current`,
  `memory.peak`, `memory.events`, PSI and selected `memory.stat` fields (`anon`,
  `file`, `shmem`, `file_mapped`, `inactive_file`, `slab`, `kernel`);
- exact owned process tree identity (PID, parent, start ticks and command-class
  hash), `smaps_rollup` RSS/PSS plus anonymous/file/shmem RSS, minor/major faults
  and CPU time for controller, worker and parser;
- samples before worker start, after ready, through per-case admission, throughout
  the case, after parser completion and after owned cleanup;
- cgroup current minus the synchronized PSS sum as a labelled diagnostic residual,
  not an exact ownership equation.

First run the existing local synthetic/trace tests, then stage telemetry by hash.
Reject on identity drift, sample gap over 1 second, PSI above zero, any OOM increment,
MemAvailable below 1.5 GiB, cleanup-boundary arrival or owned-process ambiguity.
Preserve the current outer admission rule (up to 180 seconds to obtain 60 continuous
seconds at 4.5 GiB and PSI zero) and current 60-second/3 GiB per-case admission.
Reserve the final 300 seconds for cleanup. No automatic retry.

Two bounded variants are reviewable:

1. **Attribution-only:** retain the 3 GiB active stop. This should reproduce the
   rejection once and reveal the composition immediately before it. It cannot
   measure a complete-run peak.
2. **Uncensored calibration:** use a separately approved sampled observation
   ceiling in the **3.5–4.0 GiB** range. These are hypotheses, not accepted limits.
   The observed censored maximum leaves 439.5 MiB (14.0%) below 3.5 GiB and 951.5
   MiB (30.3%) below 4 GiB. If only one calibration window is approved, 4 GiB is
   more likely to avoid another censored trace; it still must stop at that value
   and preserves all VM/PSI/OOM/time/cleanup guards. A crossing proves only that
   the candidate was too low.

At the stopped sample the VM still had 7.947 GiB available, so the evidence supports
evaluating this bounded range on the same 12 GiB VM. Recheck admission and current
identity at execution time; the historical reading does not reserve future capacity.

## How to choose a qualification ceiling afterward

Do not derive a ceiling until a fresh case completes and cleanup is observed. Let
`P` be the largest decomposed cgroup peak across the intended fresh/restored/replay
lifecycle, including final samples. For this small fixed qualification set, review
a candidate of:

`round_up_256MiB(P + max(512 MiB, 20% of P))`

The 512 MiB/20% term is a review range for allocator, cache and sampling variation,
not a production guarantee. Repeat the fixed lifecycle if the first complete trace
has a growing post-case baseline, peak at a sampling boundary, unexplained residual
over 256 MiB, or less than 10% observed cleanup release. Keep the sampled
qualification ceiling distinct from any later Pod limit.

If a Kubernetes hard limit is later proposed, first repeat the same test in a
single-container owned Pod/cgroup. Set a candidate hard limit above the qualified
ceiling with at least another `max(512 MiB, 10%)` enforcement margin, then validate
no `memory.high/max`, OOM, eviction or restart events. Process-mode evidence alone
cannot approve that limit.

## Qualification-ceiling change option

If decomposition shows expected owned-workload growth and a complete trace stays
within the reviewed envelope, changing only `max_cgroup_bytes` is the minimal path.
It affects admission/stop evidence and needs a new authorization, but it does not
change output compatibility or the frozen parser method. Fresh, restored and exact
replay still need all ACL oracles and complete graph checks; a resource PASS alone
does not accept fixture 09 or close #51.

## Lifecycle optimization option

Consider code changes only if an isolated/decomposed trace shows that owned parser
anonymous memory dominates, fails to release between cases, or exceeds a capacity
envelope main will support. Candidate experiments include explicit parser recycle
between cases, releasing model/page resources after the request, or moving work to
an owned cgroup. Each must first demonstrate lower decomposed peak without changing
the ACL graph, equations, equation-2 `TextItem`, source evidence or required OCR.

Any producer or method/profile change requires a new frozen baseline and
compatibility/reuse proof. Do not reinterpret old requests or copy registrations.
This option has more integration risk than calibration and is not supported by the
current censored trace alone.

## Handoff decision

The next main-session decision is whether to authorize one fresh-only telemetry
window with (a) the unchanged 3 GiB stop for attribution, or (b) a provisional
3.5–4.0 GiB observation ceiling to seek an uncensored peak. The report recommends
measurement/isolation calibration before changing processing code. Restored and
exact replay remain gated on a fresh result that completes within the newly reviewed
resource envelope.
