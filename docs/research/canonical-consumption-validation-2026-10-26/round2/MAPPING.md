# Round 2, phase 1d — rule mapping

Phase-1, phase-1b and phase-1c artifacts are preserved under `phase1-`,
`phase1b-` and `phase1c-` prefixes, each with a SHA-256 manifest. Frozen replay
helpers load the corresponding modules and write only inside their own
`<phase>-replay-output/results/` directories. Archived documents retain their
original artifact names in prose; their files now carry the phase prefix.
Round 1's `../part_b.py` stays untouched and retains its
atomic check/write. Current round-2 tables use **two-step V1 only**.

## Interpretations and tensions

- V4's snapshot may contain **two observations for one fact key**: the old store
  payload as included and a newer unfinished registration as pending. The mirror
  is still keyed by `(Build, uid, resource)`, so it cannot hold both facts. Pages
  retain both observations; replacement uses the newest unfinished registration
  for that key (pending precedence), otherwise the stored entry. Both payloads
  remain inspectable in the snapshot/trace. Counts/digests compare one fact per key.
- SC21 now comes from the actual phase-1 V2/W-real/seed-0 cycle, reduced
  to one obstructed key and one unrelated version allocation. No failed retry,
  lost completion, or invented crash mechanism is required. Details and reduction
  checks are in `phase1c-SC21-WITNESS.md`; all four candidate witnesses were inspected.
- SC18 follows the corrected phase-1c expectation: V4 and V4−Rb PASS, with
  `already_invalid_landings=0` and `>=1` respectively. S2/S3 remain metrics.
- **1(a) is a harness bug.** `phase1-MAPPING.md`'s SDK retry lifetime row
  explicitly covered “deltas and snapshot transfers” and said “timed-out snapshot
  aborts and restarts.” Phase 1b carried forward phase-1 interpretations, and its
  transfer-lifetime row did not explicitly repeal that deadline. The V4 path
  omitted the deadline, letting immutable pages survive indefinitely. This fix
  restores that documented rule; it does not alter snapshot content or replacement
  semantics. Regression checks reproduce the stale-view failure through N-viewexp,
  check the exact deadline boundary and test the expiry guard independently.
  All requested baseline/mutation smoke cells are rerun after the fix.
- Every V4 replacement view has `issued=view_time`; it must complete at age <90.
  At age >=90 the platform discards the transfer before installing any entries,
  then requests a fresh view. Arrival and timeout ties expire, matching the SDK's
  existing `age >= RETRY_LIFETIME` give-up rule. Old/duplicate pages cannot complete
  a discarded transfer. An announced-restore gate remains active across restarts.
- Replacement expiry checks reuse the report predicate exactly:
  `original_fact_version <= expired_version AND view_time < tombstone_expiry`.
  This is evaluated on each candidate that would be installed, **before** stamping
  W. Using W for this check could hide an old entry behind another key's newer
  counter. The brief does not specify how a rejected entry affects an atomic full
  replacement: this model rejects the entire view without partial mutation and
  requests a fresh repair, just as report rejection requests the snapshot path.
  Facts >W still survive and absent keys still become removed tombstones at W.
  N12 accepts expired references for reports and replacement entries; it retains
  the transfer lifetime. N-viewexp disables only view lifetime and replacement-entry
  expiry rejection; ordinary report expiry rejection and the Build fence remain.
- N2 remains **masked by the V4 fence**, and N-fence on NC2 is now explicitly
  **masked by tombstone**. Both cells expect PASS. N-fence removes only the two
  replacement-fence report guards and retains all other V4 rules, including the
  newly completed view rules. **NC3 is dropped by the main-line decision:** an
  absent mirror key that never registered cannot precede a V4 store write.
  Pending-before-write, W-stamped replacement tombstones and the retained expiry
  fence appear to make the replacement fence redundant. This is a claim, not a
  proof; V4 keeps its fence. Phase 2 will test N-fence on W-real, W-rewind and
  W-drift with 1,000 seeds each. Those batches are **not run in phase 1d**.
- The restore runbook is atomic with mirror rewind: install the restored facts,
  enable the gate, invalidate any pre-restore repair and request a fresh view.
  All variants use their own protocol (V1–V3 mark-and-sweep; V4+ replacement).
  **Scope interpretation:** latch the union of uids with ANY pre/post-restore fact
  in that Build, including removed tombstones, and add all fact uids accepted
  while restoring. The gate covers those documents across resources until repair
  completion, even if their fact expires meanwhile; unrelated documents remain
  ungated. The brief does not specify whether to shrink scope dynamically or how
  to handle an already-active repair. Latching avoids expiry reopening judgment;
  taking a fresh view ensures completion really repairs the restored database.
  These choices are explicit extensions at the ambiguous edges of the runbook.
- `restore_gate_flips` counts deleted-document true→false transitions while that
  document's restore gate applies. They do not fail. Liveness-gate flips remain
  separate; restore takes attribution precedence if both gates apply. Ungated
  fact-driven reversals, including after completion, increment
  `fact_based_flip_backs` and fail `S1_flipback`. Raw `flip_backs` includes all three.
- SC20 is split per the new brief: **SC20r** announces its restore, requests
  own-protocol repair and applies the document gate; all variants expect PASS.
  **SC20u** silently rewinds the same mirror to the same saved state with equal
  counts and no runbook; V1/V2 expect L2 FAIL, V3/V4 digest repair PASS.
  W-drift uses the same t500/t200 fact-mirror restore as W-rewind but silently;
  its counts may match or differ by seed. It changes no stores, counters, fences,
  SDK epochs or expiry metadata. Silent drift neither gates judgments nor aborts
  existing repairs. An existing transfer can still complete normally; heartbeat
  detection or other already-scheduled repair work can resolve the drift.
- A silent restore can immediately reintroduce included facts for an already
  enforced deleted document. The next heartbeat can repair the mirror but cannot
  erase the earlier fact-based flip-back. These remain failures under the current
  safety rules; W-drift results must therefore be distinguished from convergence.
- Failed registrations remain in the projection's unfinished-registration map
  until the uid is retried/superseded. A new attempt replaces prior intents for
  its serialized uid/page family. Removal or a no-op abandonment clears obsolete
  intents; the next age-triggered snapshot can then tombstone their mirror facts.
- Pending age starts at the original register time and is preserved in snapshot
  pages. A replacement does not make an old pending intent young again. A fresh
  retry registration starts a new age. Included snapshot state clears pending.
  One-shot timers request prompt repair; each heartbeat also scans old pending
  facts so a restored fact or a timer that fired during an existing repair cannot
  remain stuck without another request.
- The brief does not specify whether a database restore also rewinds the new
  replacement fence. W-rewind retains its original **fact-mirror-only** scope:
  it restores facts and their timestamps, but not the Build fence. A restore of
  fences as well would be a different workload; these results do not cover it.
- Late landings count actual included **source entries** written (each Wiki source
  once per page transaction), separately for ineligibility and revision drift;
  the combined count counts a source once if either holds. We also record the
  number of page/document transactions with any late source. Rb can admit an
  already-invalid non-trigger source, so those entries are counted separately
  from sources that were valid at check/register and became late afterward.
- The liveness-loss hold can extend a post-check write by at most 55 ticks beyond
  its scheduled delay (40 max): a conservative upper bound is 95. `PENDING_MAX=150`
  exceeds this. Transport/report delay is not store-write delay. Failed attempts
  and retries are separate attempts; no finite bound on repeated failures is claimed.
- The phase-1 interpretations remain unless changed here: permanent deletion;
  withdrawal/rebinding obligations superseded by reinstatement; immediate global
  liveness gate; compact per-key expiry-reference metadata; strong atomic snapshot
  view; source/profile/Build lifecycle and per-projection coalescing from round 1.

## Rules → implementation

| Rule | Function(s) in `model.py` |
|---|---|
| Fair V1 validates, then delays write; no register/pending | `finish`, `write_attempt`, `registered` |
| Fresh reads, source-profile inclusion, canonical equality and block checks | `dispatch`, `desired`, `current`, `blocked`, `valid` |
| Bootstrap start precedes enumeration; retained Builds consume; retirement clears | `new_build`, inherited lifecycle `action`, `poll`, `enumerate`; round-2 lifecycle hooks |
| Cursor acknowledgments advance monotonically; expiry fixes start before enumerate | `cursor_report`, `resync` |
| Global liveness gate; V1 included-only and V2+ included-or-pending enforcement | `any_lost`, `enforced`, `safety` |
| V1–V3 retain confirmed-flag repair | `start_snapshot`, `maybe_sweep` |
| V2/V3 register pending; same-version confirmation | `register`, `write_attempt`, `apply_fact` |
| V3/V4 stable count + XOR digest heartbeat | `digest`, `mirror_entries`, `mismatch`, `heartbeat` |
| V4 capture counter W + full store + unfinished registrations atomically | `start_replacement` |
| V4 asynchronous duplicate/reordered snapshot pages, deduplicated receipt | `replacement_page` |
| V4 view-time SDK deadline, discard and fresh view; N-viewexp omits | `start_replacement`, `replacement_page`, `replacement_deadline`, `discard_replacement` |
| Expired-tombstone fence also checks replacement entries before atomic installation | `expired_reference`, `report`, `finish_replacement`, `discard_replacement` |
| V4 atomic replacement of ≤W facts; preserve >W facts; absent tombstones | `finish_replacement` |
| V4 replacement fence rejects later ≤W reports | `fenced`, `report`, `apply_fact` |
| N-fence removes only the replacement fence; ordinary highest-version rule stays | `fenced`, `report`, `apply_fact` |
| Operator-known restore immediately gates and requests fresh repair, all variants | `restore_mirror`, `force_snapshot` |
| Restore scope includes any fact state, latched pre/post plus arrivals | `restore_mirror`, `apply_fact`, `restore_gated`, `enforced` |
| Gate ends atomically with own-protocol repair completion | `maybe_sweep`, `finish_replacement`, `restore_complete` |
| Restore-gate flips separate from fact-based and liveness-gate flips | `safety` |
| Silent drift bypasses only runbook/gate, not heartbeat detection | `workload`, `action`, `restore_mirror(announced=False)`, `heartbeat` |
| V4 successful write uses fresh confirmation version | `write_attempt` |
| V4 pending-age repair and periodic scan of restored/previously suppressed facts | `apply_fact`, `pending_expired`, `heartbeat`, `finish_replacement` |
| Ra store-extra reconciliation after expired cursor; V4−Ra omits | `resync` |
| Rb all-source page validation; V4−Rb checks trigger only | `checked_sources`, `register` |
| N2 deletes absent replacement keys; fence remains | `finish_replacement` |
| N12 accepts expired-tombstone references; lifetime and Build fence remain | `report`, `finish_replacement` |
| N-viewexp omits both replacement-transfer guards only | `start_replacement`, `replacement_page`, `finish_replacement` |
| SDK retry deadline + snapshot; TTL and expiry-reference identity | `sdk_deadline`, `outbox_send`, `gc_tombstones`, `report` |
| Durable Build counter, dirty-bit reruns, source-pass coalescing, retirement | inherited `changed`, `signal`, source-pass methods and lifecycle; `complete_attempt` |
| Included-only readiness behind serving/profile/backfill gates | `readiness`, `ready_facts` |
| Late observations and per-run source/transaction counters | `write_attempt`; `smoke.py: statistics`, `write_report` |

## Invariants and metrics → predicates / evaluation

| Item | Exact predicate / observation | When |
|---|---|---|
| S1 | deleted(D) ∧ enforced(D) ⇒ no non-retired store/page source contains D | every atomic event boundary |
| S1 flip-back | deleted(D) ∧ previously_enforced(D) ∧ ¬enforced(D) | every boundary; fact-driven reversal fails; liveness/restore-gate reversal separately counted; ungated reversals fail |
| Restore-gate metric | deleted(D) ∧ previously_enforced(D) ∧ ¬enforced(D) ∧ restore_gated(D); increment `restore_gate_flips`, no failure | every boundary |
| S7 | any non-retired Build liveness-lost ⇒ no true enforcement judgment | every boundary |
| S2 late metric | source was eligible at check/register, but `blocked(uid, resource)` at write | inside store transaction; never fails run |
| S3 late metric | source revision equalled `current(uid)` at check/register, but differs at write | inside store transaction; never fails run |
| Combined late metric | source satisfied full admission at check/register and has S2 or S3 drift at write | inside store transaction; once per source, plus transaction count |
| Already-invalid metric | source did not satisfy full admission at check/register and is invalid at write | inside store transaction, e.g. Rb; separate from late landings |
| L0 | bound hit after external workload, queue contains only repair/report/age/deadline work | FAIL with cycle evidence; other bound hits UNKNOWN |
| L1 | every non-retired store equals desired inclusion map; Wiki pages equal grouped desired sources | quiescence |
| L2 | every non-retired included fact map equals store entry-by-entry | quiescence |
| L3 | every local/reported cursor equals feed tail, including valid expiry resync | quiescence |
| L4 | no non-retired pending facts | quiescence |
| L5 | final deleted/withdrawn and still-moved-out scopes are enforced | quiescence |

Enforcement is globally false while any non-retired Build is liveness-lost;
restore-gated documents are also false; otherwise it is absence of included facts (V1) or included/pending facts (V2+).
`current(uid)` is None for deleted/withdrawn documents, otherwise canonical revision.
Explicit blocks deny eligibility without erasing canonical revision.

## Fault → expected absorption / detection

| Fault | Mechanism / limitation |
|---|---|
| Delay, duplication, reorder | highest versions; V4 page IDs + replacement fence; fresh confirmations |
| Failed/slow attempts and post-register write failures | serialized fresh retries; V4 includes unfinished registrations in view |
| Lost confirmation in crash | V4 pending-age repair sees completed store as included; V3 payload-equal pending may stick |
| Liveness loss | global enforcement gate; finite recovery; no heartbeat from lost projection |
| Consumer paused beyond retention | fix new feed start, enumerate, reconcile store extras (Ra) |
| Wiki source changes | all-source check/register (Rb); delayed landing measured, S1/L1/L5 still checked |
| Announced fact-mirror rewind | immediate own-protocol repair plus document-scoped restore gate; count/digest monitoring continues; V4 fence and projection state survive |
| Silent fact-mirror drift | count/digest heartbeat only; equal counts evade V1/V2; early fact-based flip-backs still fail |
| Replacement pages arriving after view deadline / tombstone expiry | active 90-tick view timeout + fresh repair; expired-reference entry rejection; N-viewexp omits both |
| Late old report after tombstone expiry | expiry-reference check (except N12); replacement fence independently rejects ≤W |
| Watermark newer than surviving store version | V4 replacement stamps snapshot observations W instead of replaying old versions |

## Scenario/control → schedule and expected verdict

| ID | Fixed schedule / mutation (`scenarios.py`) | Expected, retained from briefs |
|---|---|---|
| SC15 | check/register+write D t=10; delete t=11; included arrives t=12; remove t=14 | V1 S1 FAIL; V2/V3/V4 PASS |
| SC16 | pause retrieval t=1..100; delete D t=10; retention expires, resync | V3/V4 PASS; V4−Ra L5 FAIL |
| SC18 | page {D,E}; E update/read t=10; delete D t=11; check/register t=12, scripted zero write delay | V3/V4 PASS; V4−Rb PASS with already_invalid_landings≥1; V4=0 |
| SC19 | D removed v100 at t=1; TTL expires t=121; old included v99 arrives t=123 | V3/V4 PASS; N12 L2 or fact-driven flip-back FAIL |
| SC20r | save mirror t0; write rev50 t10/report t11; equal-count announced rewind t20, immediate runbook | V1/V2/V3/V4 PASS |
| SC20u | identical state and t20 rewind, silent; no gate or repair request | V1/V2 L2 FAIL; V3/V4 digest repair PASS |
| NC2 | delete/remove t1, report lost; empty repair t2..4; old included v99 t5 | V3/V4 PASS; N2 PASS masked by V4 fence; N-fence PASS masked by tombstone |
| NC3 | dropped: never-registered mirror key with a V4 store write is unreachable; no impossible fixture or extra silent-rewind fault added | no cell; redundancy claim reserved for phase 2 |
| SC21 | store D rev1/v1, E v3; D current rev50. Register D v4 at t10, delayed write t15. Withdraw/remove E v5 at t11; snapshot W5 at t12; sweep t14 tombstones D; confirmation v4 at t16 rejected. Repeated snapshots replay v4 below v5 | V2/V3 L0 FAIL; V4 PASS: view includes unfinished D, stamps pending W5; fresh successful confirmation v6 accepted |
| SC22 | Wiki page write succeeds; crash before unsent confirmations; included+pending payloads match | V3 L4 FAIL; V4 pending-age repair PASS |
| SC23 | register v8 t=10; allocate W=9 and capture in-flight view t=11; delete t=12; write lands t=15 | V4 S1 holds, fresh confirmation >W accepted; removal + enforcement; PASS |
| SC24 | D stored/mirrored rev1/v1; view W1 at t10; delete t11; remove/store+fact v2 t12 (expiry t132); original last page t135. V4 timeout t100, fresh view W2 finishes t101; N-viewexp waits until t135 | V4 PASS; N-viewexp S1_flipback OR L2 FAIL |
| V4−Ra / V4−Rb | remove exactly the corresponding baseline rule | no prescribed random-seed outcome; targeted rows above |
| N2 / N12 / N-fence / N-viewexp | V4 absent-key deletion / expired-reference acceptance / Build-fence removal / both replacement-transfer guards removed | NC2 masking accepted; N12 SC19 FAIL; N-viewexp SC24 FAIL |

## Parameters and remaining choices

| Choice | Value |
|---|---|
| Population / pages | eight documents, two sources/resources/projections; stable same-resource pairs d0/d2, d1/d3, d4/d6, d5/d7, split on move |
| Feed retention / tombstone TTL / SDK deadline | 60 / 120 / 90 ticks, unchanged from phase 1 |
| Heartbeat / pending age | 17 ticks / PENDING_MAX=150; expiry event at original pending time +151 |
| Read/attempt delay | 1–9, or 15% slow 25–85; attempt failure 12% |
| Post-check/register delay | all variants 1–6, or 15% 15–40; scripted zero/explicit delays only to isolate requested schedules |
| Script follow-up | `FixedSchedule` uses the minimum delay in each inherited scheduling interval, no shuffle, no random failures; all mandated script anchors use explicit timestamps, rather than sampling a scenario seed |
| Store failure | 12% after accepted check/register, applied equally to fair V1 and V2+ |
| Delta transport | outbox 1–4; 1–3 copies per send; delay 1–40 or 10% 90–180; failures 12%; deadline below TTL |
| Replacement pages | immutable entries (included and pending separately), two records/page; same 1–3 copies and 1–40/90–180 delays, 12% receive retry; all page IDs required before replacement |
| Replacement ordering | union of current and snapshot keys; >W preserved; snapshot missing key tombstoned at W; pending wins same-key collision |
| Restore runbook / scope | immediate fresh repair; any-fact pre/post/arriving uid union latched until atomic completion; counters and gate state do not rewind |
| Mirror-only rewind | serving retrieval Build at t=500, own mirror from first boundary at/after t=200; store/counter/intents/replacement fence unaffected |
| Workloads | W-real unchanged; W-rewind adds announced t500 restore; W-drift adds silent t500 mirror rewind to t200, equal or unequal counts by seed; no arbitrary corrupt_revision/drop actions |
| Crash persistence | Build counters, stores, unfinished registration intents and attempt retries survive; unsent report/retry records are invalidated by projection epoch, as in phase 1 |
| Liveness / crash / retention pause | wiki loss t=100..155; crashes retrieval245/wiki250; retrieval pause5..125 on even seeds |
| Bound / quiescence | 30,000 events; no repeated-state early pass; L1–L5 only when queue drains |
| Costs | per-seed snapshot starts, mean / nearest-rank p95; transient counterfactual as phase 1, noting RNG-consumption sensitivity |
| Late statistics | per-run source counts and transaction counts; aggregate mean / nearest-rank p95 / max over five seeds; bound-hit observations censored |
| Snapshot transfer lifetime | 90 ticks from immutable view capture; unfinished V4 transfer aborted and replaced by a fresh view; stale pages ignored; N-viewexp has no view deadline |
| Replacement expiry handling | same retained per-key expired-version/expiry metadata as reports; use original entry version and view time; any rejected installed candidate aborts whole view before mutation |
| SC24 transport | one-record view, last page delayed 125 ticks (inside the modelled 90–180 slow-delay range); fresh view pages use deterministic 1-tick follow-up |
| Phase-2 fence experiment | future N-fence on each of three workloads, 1,000 seeds each; not authorized to run in this phase |

Final observations and deviations are generated in `SMOKE.md`; full batches are
intentionally excluded from phase 1d.

## Verification and preservation

All superseded phase-1c files were preserved before edits; `phase1c-manifest.json`
records their hashes and `phase1c-replay.py` replays frozen code in isolation.
Earlier archives and round-1 files remain untouched. The current smoke runner
checks the round-1 code hash and passed 30 targeted protocol checks before executing
exactly 90 random cells (seeds 0–4) and the complete 33-cell deterministic matrix.
The final audit verified all 24/35/42 archived phase-1/1b/1c hashes, raw-cell
coverage, recomputed cost/landing statistics, flip classification and the ordered
30-line SC24/V4 trace. A frozen phase-1c replay matched its original JSON result
exactly. Current SC24/V4 and V4/W-drift/seed-4 replays matched across two Python
hash seeds. Round-1 code and MODEL.md hashes remain unchanged. Full results and
findings are in `SMOKE.md`. No full batches, network calls or GitHub operations.
