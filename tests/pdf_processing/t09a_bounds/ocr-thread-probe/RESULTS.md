# OCR native-thread diagnosis (CT–CX)

Diagnostic only. No production source, acceptance standard, deployment replica,
object limit, PVC, or existing object prefix was changed. All 32 held Deployments
remained off. Each run used a fresh identity, one attempt, and container removal.

## Finding

The installed RapidOCR default creates three ONNX sessions with backend-default
intra-op pools. In CT2, a container with a 4-CPU quota still exposed an affinity
of 18 CPUs. Each session added 17 threads: 7 before initialization, 58 after,
61 after inference. This proves pool oversubscription relative to the quota;
it does **not** identify historical CS host TGID 1018098 as that OCR process.

CU changed only `EngineConfig.onnxruntime.intra_op_num_threads` to 4 in a
throwaway source copy. Engine-ready threads fell to 16 (19 after inference).
The complete OCR report except its existing timing field matched CT2 exactly;
the PNG bytes also matched. Observed inference time fell from 1.1216 to 0.5137
seconds in these single runs. Minor faults did not fall: 340621 versus 345248.
Both isolated runs had zero VM full PSI delta. Therefore the thread bound is
an output-preserving performance candidate, **not a proven fix for CS PSI**.
No production patch is justified by these measurements alone.

## Controls and limitations

| Run | Change / result |
| --- | --- |
| CT | Observer source-relative path was wrong; instrumentation failed. OCR outputs existed but no valid phase attribution. Retained, not counted as a pass. |
| CT2 | Corrected observer source path; default OCR alone passed. |
| CU | Only intra-op pool bound changed to 4; OCR outputs/crop matched and resource guards passed. |
| CV | Added real Wiki06 native capture and retained parser, but inherited the old OCR probe's THP-enabled wrapper. Stopped before OCR; compact_stall +76. This differs from CS and cannot explain CS, whose pressure window had compact_stall +0. |
| CW | Matched actual CS inherited THP-disabled supervisor policy. Old probe stopped on a 6us global cumulative PSI increment before OCR; avg10=0, no direct scan/allocstall/compaction delta. Not the CS stop criterion. |
| CX | Matched existing CS VM full avg10=0 predicate; retained cumulative values. Real 28-page native capture plus resident parser plus default OCR completed in 48.90s. VM avg10 remained 0, cumulative +132us; no OOM/max event. |

CX deliberately uses the original CS VM stop predicate, not a new acceptance
threshold. `policy-comparison.json` records execution of the exact existing guard:
CW's sample passes it, while CS's 0.18 trigger fails it. Automatic review first
rejected execution as a possible relaxation; after that source-and-sample check,
the equivalent-policy diagnostic was approved and executed. CX additionally
retains the isolated probe's cgroup avg10, max-event, memory and deadline checks.

The preserved input is Wiki06 `#/pictures/0` from the prior OCR probe, with the
same source and reviewed geometry. CS assembly-byte equivalence was not freshly
established; this is a component diagnostic, not restored/exact-replay acceptance.
CX captures a real parser after whole-document native capture; it does not
reproduce CS's grouped capture/assembly sequence, Pod cgroup ancestry, object
traffic, or 32-on normal service load. Its pass excludes an unconditional failure
of this overlap, not a load-sensitive failure. The host snapshot maps only the
live warm parser; it does not recover CS's missing OCR host/container PID mapping.

## Current causal classification and next step

CS still demonstrates real allocator/reclaim pressure, then VM guard stop, then
workflow cancellation/business failure. There is no evidence that Activity
failure caused the guard. The precise active library pool, per-zone allocator
watermarks and necessity of resident-parser overlap under normal load remain
unknown. Global MemAvailable and absence of OOM do not disprove reclaim stalls.

Do not rerun a full matrix or promote the thread bound yet. The next useful
measurement is the **first component under the existing normal topology**, with
host NSpid/start-time mapping captured at the allocation event and phase/thread
markers. Preserve CS's THP policy, grouped capture and all current guards. Compare
the 4-thread candidate only if the default reproduces the same allocator path;
otherwise report that the causal hypothesis was not established. No new hardware
or memory/PSI relaxation is indicated by these results.

## Cleanup and ticket status

All six owned diagnostic containers were removed; independent post-run checks
confirmed 32 Deployments off and object 512Mi Ready. CX parser was reaped without
forced kill. No normal-topology qualification or full fixture graph was completed.
This adds evidence to the remaining #44 diagnosis; it does not reopen completed
#51/Q04, satisfy #44 bounds, or unblock #45. Issue update text remains local.
