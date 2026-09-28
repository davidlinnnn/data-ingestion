# YOLO fixture-window resource candidate

The retained 397-sample attribution stream has one 4 GiB violation. It occurs
inside the third sequential group request while PID 3486 is the only model-heavy
process. There is no fresh parser at the peak, so the earlier overlap defect is
resolved.

This inactive candidate changes only the fixture-window parser budget:

```json
{"max_requests": {"before": 20, "after": 1}}
```

All startup, no-progress, terminate, and reap budgets remain unchanged. No
production source changes. Recycling after each group request is the smallest
candidate supported by the retained evidence: the same PID served all three
groups with zero recycles, while its reported RSS high-water increased from
1,820,176 to 1,906,860 to 1,994,884 KiB; only group 3 crossed the limit.

[`BUNDLE.json`](BUNDLE.json) fixes the source failure, allowed diff, unchanged
4 GiB threshold, and future all-complete-sample gate. That gate requires both
cleanup markers on the final sample, rather than accepting an earlier marker.
The validator result in
[`evidence/validation.json`](evidence/validation.json) keeps the candidate
`runtime_active=false`. It is not authorization for another window.

If a later approved fixture-07 run still violates the same gate, stop lifecycle
tuning and use a dedicated cgroup or separate Linux validation host. Apply the
same 4 GiB threshold to every complete 250 ms sample, with
`owned_cleanup_finished` and `post_cleanup_sample` on the final sample;
do not raise the limit or add another collector.
