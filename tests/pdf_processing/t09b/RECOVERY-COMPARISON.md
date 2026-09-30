# T09b matched native recovery comparison

RA2 (group 5) and RB1 (group 10) interrupt one active child after the same
10 durable pages. Same native51 source, seven required OCR components, model,
resources, reference oracle and finite recovery policy. Both complete all 51
pages with exact document/checks equality, complete traffic evidence and cleanup.
RA1 failed at pre-inference imports and is excluded; its evidence is retained.

| Measurement | RA2 group 5 | RB1 group 10 |
| --- | ---: | ---: |
| Loss to business completion, seconds | 112.7156–112.7365 | 116.5663–116.5868 |
| Repeated pages | 5 (11–15) | 10 (11–20) |
| Retained registered groups | 2 | 1 |
| Server HTTP TX bytes | 1,614,996,847 | 1,867,302,641 |
| Server HTTP RX bytes | 149,278,025 | 149,011,515 |
| Application read amplification | 10.5981 | 12.2779 |
| Whole-Pod sampled peak bytes | 2,497,429,504 | 2,525,315,072 |
| Unique registered payload bytes | 148,681,815 | 148,392,910 |
| Total current prefix bytes | 177,937,087 | 177,638,842 |
| Orphan attempt objects | 0 | 0 |

One fault pair does not establish a recovery distribution or reliability SLA.
Group 10 repeats twice as many pages and transfers about 15.6% more server TX
in this case, with recovery about 3.85 seconds longer. Together with overlapping
normal-path times (three matched pairs, about 1.7% median gain), this supports
retaining group 5 and one active parser child. No accepted bound is increased.

## Remaining acceptance work

- Process-cold fixture coverage is now measured at n=3; see COLD-WARM-DISTRIBUTIONS.md.
- Resolve total retained/native buffering measurement; publication/read-chunk sizes are partial.
  Stage scopes are now reported separately in cold cell stage-cost.json and timing reports.
- Resolve the conditional concurrency requirement: two children remain not
  admitted without a reviewed aggregate budget under existing limits. This is
  not evidence of a measured two-child runtime failure.
- Consolidate final supported file/page/pixel, memory, timeout, retry/no-progress,
  recycle and drain bounds, with targeted requalification if anything changes.

#45 remains open. #44/#51 proofs retain their historical scope. Main is unchanged.
