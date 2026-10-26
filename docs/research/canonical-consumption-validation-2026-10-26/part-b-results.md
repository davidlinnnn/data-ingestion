# Part B — design

Counts are seeds with ≥1 violation, not number of failing event boundaries. Liveness is evaluated only after quiescence. UNKNOWN is separate from zero violations.

| Variant | Seeds | S1 | S2 | S3 | L1 | L2 | L3 | Nonquiescent / UNKNOWN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| design | 1000 | 678 | 0 | 0 | 0 | 943 | 0 | 0 |

## design

Deleted-document S1 witnesses: 28 seeds. Quiescent runs: 1000.

Aggregate exercise counters: `{"S1_deleted_checks": 702, "action_build": 2000, "action_corrupt_drop": 1000, "action_corrupt_revision": 1000, "action_delete": 2000, "action_method_refresh": 9602, "action_profile": 3000, "action_rebind": 7575, "action_retire": 2000, "action_rollback": 9668, "action_source_update": 9689, "action_switch": 2000, "action_switch_back": 960, "action_withdraw": 7466, "attempt_failures": 17750, "attempts": 149285, "commits": 71264, "corrupt_drop": 2000, "corrupt_revision": 999, "cursor_retry": 7126, "heartbeat_mismatches": 28756, "old_reports_ignored": 21268, "readiness_serving_only_checks": 2500159, "report_copies": 173745, "report_retries": 35114, "rerun_signalled": 47730, "slow_attempts": 22471, "snapshots": 17727, "source_pass_coalesced": 1761, "source_passes": 6000, "superseded": 15938, "wiki_batch_1": 41930, "wiki_batch_2": 15608, "wiki_batch_3": 3800, "wiki_batch_4": 751, "wiki_batch_5": 91}`

### S1 — smallest failing seed in the tested range: 0

`{"deleted": false, "reason": "no included fact in any non-retired Build", "stores": [["retrieval-0", "r0"]], "uid": "d3"}`

```text
0141 fact ('wiki-1', 'd1', 'r0') included=False rev=None v=6
0142 superseded retrieval-1 d5 wanted=('r0', 14) current=18 blocked=False
0143 fact ('wiki-1', 'd6', 'r0') included=False rev=None v=8
0143 read retrieval-0 d5 desired=('r0', 18) delivered=32
0143 read retrieval-1 d2 desired=('r1', 20) delivered=32
0144 commit wiki-0 [(('d7', 'r0'), True, 15, 27)]
0145 fact ('wiki-0', 'd1', 'r0') included=True rev=19 v=25
0145 commit retrieval-1 [(('d4', 'r1'), True, 16, 8)]
0146 fact ('retrieval-1', 'd0', 'r0') included=True rev=1 v=2
0146 sweep tombstone ('retrieval-1', 'd3', 'r0') v=5
0146 snapshot 5 end
0146 fact ('retrieval-1', 'd7', 'r0') included=True rev=9 v=7
0146 read retrieval-0 d3 desired=('r0', 4) delivered=32
0146 read retrieval-1 d6 desired=('r0', 7) delivered=32
0147 read wiki-1 d2 desired=None delivered=32
0147 read wiki-1 d7 desired=('r0', 15) delivered=32
0148 fact ('retrieval-1', 'd1', 'r0') included=True rev=19 v=6
0148 fact ('retrieval-1', 'd4', 'r1') included=True rev=16 v=8
0149 fact ('wiki-1', 'd1', 'r0') included=True rev=19 v=10
0149 commit retrieval-0 [(('d3', 'r0'), True, 4, 16)]
```

### S1_deleted — smallest failing seed in the tested range: 0

`{"deleted": true, "reason": "no included fact in any non-retired Build", "stores": [["retrieval-1", "r0"]], "uid": "d0"}`

```text
0234 read wiki-0 d2 desired=('r0', 21) delivered=42
0234 read wiki-1 d6 desired=None delivered=42
0235 fact ('retrieval-0', 'd7', 'r0') included=True rev=15 v=24
0240 attempt failed wiki-0 ['d2']
0240 read wiki-0 d2 desired=('r0', 21) delivered=42
0242 action withdraw ['d2', True]
0242 feed 43 current_revision_changed d2
0242 fact ('wiki-0', 'd5', 'r0') included=True rev=22 v=29
0242 read wiki-1 d2 desired=None delivered=42
0243 fact ('wiki-0', 'd4', 'r1') included=True rev=16 v=28
0244 commit wiki-0 [(('d1', 'r0'), False, None, 31)]
0245 read wiki-0 d1 desired=None delivered=42
0246 fact ('wiki-0', 'd5', 'r0') included=True rev=22 v=29
0246 deliver retrieval feed=43 current_revision_changed d2
0246 deliver wiki feed=43 current_revision_changed d2
0247 action switch_back ['retrieval']
0247 serving retrieval-0
0247 action corrupt_drop []
0247 corrupt_drop ('wiki-0', 'd5', 'r0')
0247 corrupt_drop ('retrieval-1', 'd0', 'r0')
```

### L2 — smallest failing seed in the tested range: 0

`{"build": "wiki-1", "facts": "{('d4', 'r1'): -999, ('d7', 'r0'): 26, ('d5', 'r1'): 18}", "store": "{('d7', 'r0'): 26, ('d4', 'r1'): 16, ('d5', 'r1'): 18}"}`

```text
0341 retire wiki-0
0342 fact ('wiki-1', 'd5', 'r1') included=True rev=18 v=15
0344 fact ('retrieval-1', 'd5', 'r1') included=True rev=18 v=21
0345 fact ('wiki-1', 'd4', 'r1') included=True rev=16 v=13
0346 fact ('wiki-1', 'd7', 'r0') included=True rev=26 v=16
0349 snapshot 18 end
0358 action retire ['retrieval']
0358 retire retrieval-1
0360 snapshot 19 end
0367 fact ('wiki-1', 'd5', 'r1') included=True rev=18 v=15
0367 sweep tombstone ('wiki-1', 'd6', 'r0') v=17
0367 sweep tombstone ('wiki-1', 'd1', 'r0') v=17
0367 sweep tombstone ('wiki-1', 'd2', 'r1') v=17
0367 sweep tombstone ('wiki-1', 'd5', 'r0') v=17
0367 snapshot 20 end
0372 backfill complete retrieval s0 profile_seq=35
0372 fact ('wiki-1', 'd1', 'r0') included=False rev=None v=17
0442 action corrupt_revision []
0442 corrupt_revision ('wiki-1', 'd4', 'r1')
0480 fact ('retrieval-0', 'd5', 'r0') included=False rev=None v=27
```
