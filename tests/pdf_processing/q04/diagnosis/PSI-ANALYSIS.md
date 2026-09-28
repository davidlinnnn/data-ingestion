# Q04 Keynote PSI offline diagnosis

Status: **cause narrowed, not proven**. This analysis uses only the retained
2026-09-16 sentinel artifacts and current read-only infrastructure observations.
It ran no workflow or inference, changed no replica, and changed no production
or frozen profile setting.

## Deterministic captured-trace check

The fast feedback loop replays the 133 captured worker samples through the
unchanged `max_full_psi=0` decision. It asserts the exact symptom, OOM invariants,
parser identity and event ordering:

```sh
python3 tests/pdf_processing/q04/diagnosis/replay_pressure.py --assert-captured
```

The command completes in under a second and reports
`RED_VM_PSI_PRESSURE`, observed 0.18 against maximum 0. It does not simulate or
rerun parser work; it proves that this immutable trace deterministically crosses
the same guard. Running without `--assert-captured` deliberately exits 1.

## Evidence-aligned timeline

| UTC time | Evidence |
| --- | --- |
| 14:36:54.293 | Temporal workflow recorded as started |
| 14:36:54.397 | workflow status became `parsing`, 0 registered pages |
| 14:36:54.421 | parser PID 9625 observation began |
| 14:36:54.783 | first sample containing parser PID; cgroup 0.448 GiB, PSI 0 |
| 14:36:59.212 | parser emitted its first `stage_enter` progress |
| 14:36:59.307 | sampler observed `stage_enter`; cgroup 1.896 GiB, PSI 0 |
| 14:36:59.808 | first positive full PSI sample, 0.18; cgroup 1.931 GiB |
| 14:36:59.890 | workflow cancellation requested |
| 14:36:59.903 | Temporal lifecycle completed with failed application result |
| 14:37:00.002 | parser reported checkpoint commit |
| 14:37:00.311 | worker stopped; parser and scratch absent |

The parser cgroup grew by 1,555,058,688 bytes (1.448 GiB) between its first
sample and the sample that first observed `stage_enter`, over about 4.52 seconds.
The first positive PSI sample followed about 0.50 seconds later. Minimum VM
available memory was 3,064,819,712 bytes (2.854 GiB), maximum cgroup usage was
2,073,538,560 bytes (1.931 GiB), global OOM stayed 28, and cgroup OOM stayed 0.

`stage_enter` is emitted inside the first native page stage. Production parser
source initializes the `DocumentConverter` pipeline and models before this event.
Therefore the large cgroup rise overlaps imports/model initialization and ends at
the initialization-to-first-stage boundary. Because PSI avg10 is a smoothed
measure, its first positive sample does not prove that the stall began after
`stage_enter`; it may summarize pressure in the preceding initialization window.
The checkpoint commit proves the parser was still making progress. These facts
exclude an OOM and support a short pressure burst, but do not identify its owner.

## Ranked, falsifiable hypotheses

1. **Insufficient VM reclaim margin during model initialization.** If this is the
   cause, releasing the additional 0.902 GiB currently used by idle historical
   PDF services should keep full PSI at zero with the same profile and cgroup
   curve. If PSI repeats with at least the Q03-D capacity level, this hypothesis
   loses substantial weight.
2. **Cold model reads/page faults cause an I/O-linked full stall.** If this is the
   cause, a higher memory baseline may still fail at the same initialization
   boundary, with rising I/O PSI, major faults or model-file read bytes. Current
   evidence did not record those counters.
3. **Another VM cgroup caused concurrent pressure.** If this is the cause, a
   host-wide container/cgroup sampler will show another workload changing during
   the same sub-second window while parser RSS alone is insufficient to explain
   it. Only the Q04 coordinator cgroup was sampled during the failed run.
4. **PSI avg10 carried a prior short event into the observed sample.** A 60-second
   admission at zero makes this less likely. Recording PSI `full total` deltas
   would falsify it by locating new stall time relative to parser events.

The evidence does not justify a parser defect diagnosis or a processing change.

## Observation gaps for a separately approved rerun

- Record PSI `some`/`full` `total` plus avg10, I/O PSI and CPU PSI at every sample.
- Record `vmstat` reclaim, compaction, swap, `pgmajfault` and OOM deltas.
- Split worker and parser PID RSS/PSS, faults, I/O bytes and CPU instead of only
  recording their shared cgroup.
- Capture host-wide container working set and CPU before parser launch and across
  the first-stage boundary; Metrics API is currently unavailable, so use CRI
  statistics as the read-only fallback.
- Add explicit parser events immediately before and after model initialization.
  The current `model_initialization` event is not forwarded through the warm-child
  progress protocol.
- Preserve monotonic timestamps for workflow, activity, parser events and resource
  sampling; current Temporal timestamps and host epoch are alignable but not from
  one clock source.

These are observation requirements for a future harness/window. They do not
authorize instrumentation, inference, profile changes or another run.
