"""Necessary post-run check: full JSON equality and real mixed-window results."""
import json
from pathlib import Path

ROOT = Path(__file__).parent
WARM = Path("/private/tmp/t09a-bounds-20260928-cs/evidence/state/bounds-pod-cgroup-cs")
rows = []
for index, sid in enumerate(("06", "07", "08", "native", "06")):
    tag = "ai" if sid in ("06", "native") else "aj"
    fresh = Path(f"/private/tmp/q04-matrix-pod-cgroup-20260924-{tag}/evidence/state/matrix-pod-cgroup-{tag}/fresh-{sid}")
    warm = WARM / f"warm-{index}-{sid}"
    load = lambda path: json.loads(path.read_text())
    assert load(warm/"document.json") == load(fresh/"document.json"), sid
    assert load(warm/"checks.json") == load(fresh/"checks.json"), sid
    assert load(warm/"result.json")["processing_complete"], sid
    assert load(warm/"accepted.json")["verified"], sid
    rows.append(sid)
proof = load(WARM/"warm-proof.json")
assert proof["groups"] == 29 and proof["recycles"] == 1 and len(proof["pids"]) == 2
trial = load(ROOT/"first-window-evidence/object-trial-cleanup.json")
assert trial["primary_error"] is None
assert trial["object_psi_policy"]["mode"] == "functional_diagnostic"
assert trial["maximum_object_full_avg10"] == 0
assert trial["object_observer"]["max_events_delta"] == 0
assert load(ROOT/"first-window-evidence/independent-cleanup.json")["status"] == "PASS"
print("PASS: five full JSON/check comparisons; 29 groups, one recycle; diagnostic object guards and cleanup")

readiness = load(ROOT/'first-window-evidence/protection-readiness.json')
assert readiness[-1]['time']-readiness[0]['time']>=125
assert load(ROOT/'first-window-evidence/independent-cleanup.json')['memory_low']['verified_restored']
print('PASS:125s protection persistence admission and manager/kernel restoration')
