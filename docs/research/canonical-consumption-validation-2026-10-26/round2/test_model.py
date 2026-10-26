"""Small protocol checks, independent of the random smoke workloads."""
import sys
sys.dont_write_bytecode = True
import unittest
import heapq
from model import Simulation, digest, RETRY_LIFETIME, PENDING_MAX, round1
from scenarios import scenario, check_expected


class ProtocolChecks(unittest.TestCase):
    def test_round1_original_checks_still_run(self):
        round1.self_check()

    def test_digest_order_independent_and_revision_sensitive(self):
        a = {('a', 'r0'): 1, ('b', 'r0'): 2}
        self.assertEqual(digest(a), digest(dict(reversed(list(a.items())))))
        self.assertNotEqual(digest(a), digest({('a', 'r0'): 3, ('b', 'r0'): 2}))

    def test_pending_blocks_enforcement_not_readiness(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        bid, key = 'retrieval-0', ('d0', 'r0')
        s.apply_fact((bid, key, True, 1, 100), 'pending')
        self.assertFalse(s.enforced('d0'))
        self.assertNotIn(key, s.ready_facts(bid))
        self.assertIn(key, s.mirror_entries(bid))
        self.assertEqual(s.readiness('retrieval', 's0'), 3)
        s.apply_fact((bid, key, True, 1, 100))
        self.assertIn(key, s.ready_facts(bid))
        self.assertEqual(s.readiness('retrieval', 's0'), 4)

    def test_payload_equal_pending_is_not_silently_confirmed(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.signal(s.builds['wiki-0'], 'd0')
        while s.q:
            if s.step() == 'write_attempt':
                # Crash between the page write and its queued outbox sends.
                s.action('crash', ['wiki'])
                break
        result = s.run()
        self.assertFalse(s.mismatch('wiki-0'))
        self.assertGreaterEqual(s.metrics['crash_lost_reports'], 2)
        self.assertIn('L2', result['violations'])
        self.assertIn('L4', result['violations'])

    def test_highest_version_tombstone_and_confirmation(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        bid, key = 'retrieval-0', ('d0', 'r0')
        s.apply_fact((bid, key, False, None, 100))
        s.apply_fact((bid, key, True, 1, 99))
        self.assertFalse(s.facts[(bid,) + key]['included'])
        s.apply_fact((bid, key, True, 2, 101), 'pending')
        s.apply_fact((bid, key, True, 2, 101))
        self.assertTrue(s.facts[(bid,) + key]['included'])

    def test_block_rejects_admission_without_erasing_canonical_revision(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.docs['d0']['blocked'] = True
        self.assertEqual(s.current('d0'), 1)
        self.assertFalse(s.valid(('d0', 'r0'), 1))
        self.assertIsNone(s.desired('d0', 'retrieval'))

    def test_retrieval_noop_does_not_register_or_report(self):
        s = scenario('SC20r', 'V2')
        s.q.clear()
        s.script_read('d0', 0)
        counter = s.builds[s.bid]['counter']
        s.run()
        self.assertEqual(s.builds[s.bid]['counter'], counter)
        self.assertFalse(any('register retrieval' in line for line in s.trace))

    def test_liveness_loss_gates_all_builds(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.facts.clear()
        self.assertTrue(s.enforced('d0'))
        s.action('liveness_loss', ['wiki', 5])
        self.assertFalse(s.enforced('d0'))
        s.time = 5
        self.assertTrue(s.enforced('d0'))

    def test_v1_delayed_by_liveness_loss_rechecks_at_write(self):
        s = scenario('SC15', 'V1')
        s.q.clear()
        s.at(0, 'script_read', 'd0', 1)
        s.at(0, 'action', 'liveness_loss', ['retrieval', 5])
        s.at(2, 'action', 'source_update', ['d0'])
        result = s.run()
        self.assertNotIn('S2', result['violations'])
        self.assertNotIn('S3', result['violations'])
        self.assertEqual(s.metrics['late_landings'], 0)

    def test_fair_v1_late_write_is_measured_not_S2_S3_failure(self):
        s = scenario('SC15', 'V1')
        s.q.clear()
        s.at(0, 'script_read', 'd0', 0, 5)
        s.at(1, 'action', 'delete', ['d0'])
        result = s.run()
        self.assertEqual(s.metrics['late_S2'], 1)
        self.assertEqual(s.metrics['late_S3'], 1)
        self.assertEqual(s.metrics['late_landings'], 1)
        self.assertNotIn('S2', result['violations'])
        self.assertNotIn('S3', result['violations'])
        self.assertIn('S1', result['violations'])

    def test_replacement_waits_for_all_distinct_pages_and_preserves_newer_fact(self):
        s = Simulation(variant='V4', actions=[], faults=False, measure_transients=False)
        s.q.clear()
        b = s.builds['retrieval-0']
        s.start_snapshot(b)
        sid, watermark = b['repair'], b['counter']
        pages = {args[1]: args[2] for _, _, kind, args in s.q if kind == 'replacement_page'}
        b['counter'] += 1
        s.apply_fact((b['id'], ('d0', 'r0'), True, 99, b['counter']))
        indices = list(reversed(sorted(pages)))
        s.replacement_page(sid, indices[0], pages[indices[0]])
        s.replacement_page(sid, indices[0], pages[indices[0]])
        self.assertEqual(b['fence'], 0)
        for index in indices[1:]:
            s.replacement_page(sid, index, pages[index])
        self.assertEqual(b['fence'], watermark)
        self.assertEqual(s.facts[(b['id'], 'd0', 'r0')]['revision'], 99)
        self.assertEqual(s.metrics['replacements'], 1)
        self.assertEqual(s.metrics['duplicate_snapshot_pages'], 1)
        self.assertFalse(s.apply_fact((b['id'], ('d1', 'r0'), True, 2, watermark)))

    def test_N2_delete_is_still_protected_by_replacement_fence(self):
        s = Simulation(variant='N2', actions=[], faults=False, measure_transients=False)
        s.q.clear()
        b = s.builds['retrieval-0']
        del b['store'][('d0', 'r0')]
        s.start_snapshot(b)
        while b['repair'] is not None:
            s.step()
        self.assertNotIn((b['id'], 'd0', 'r0'), s.facts)
        self.assertFalse(s.apply_fact((b['id'], ('d0', 'r0'), True, 1, 1)))

    def test_snapshot_includes_stored_and_inflight_pending_observations(self):
        s = scenario('SC21', 'V4')
        result = s.run()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertTrue(any('included rev=1 original_v=1' in line for line in s.trace))
        self.assertTrue(any('pending rev=50 original_v=4' in line for line in s.trace))
        self.assertTrue(any('confirm_v=6' in line for line in s.trace))

    def test_minimized_actual_witness_cycles_without_suppressing_a_retry(self):
        for variant in ('V2', 'V3'):
            s = scenario('SC21', variant)
            result = s.run()
            self.assertEqual(set(result['violations']), {'L0'})
            self.assertTrue(check_expected('SC21', variant, result))
            self.assertEqual(s.metrics['store_write_failures'], 0)
            self.assertEqual(s.builds[s.bid]['store'], {('d0', 'r0'): 50})
            self.assertFalse(s.builds[s.bid]['jobs'])

    def test_N_fence_keeps_highest_version_and_tombstone_rules(self):
        s = scenario('NC2', 'N-fence')
        result = s.run()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertTrue(check_expected('NC2', 'N-fence', result))
        self.assertEqual(s.metrics['fenced_reports_ignored'], 0)
        self.assertEqual(s.metrics['old_reports_ignored'], 1)
        # Equal-version reports demonstrate that only the fence was removed.
        b = s.builds[s.bid]
        self.assertTrue(s.apply_fact((s.bid, ('d0', 'r0'), True, 1, b['fence'])))

    def test_SC18_measures_Rb_without_failing_invariants(self):
        for variant, invalid in [('V4', 0), ('V4-Rb', 1)]:
            result = scenario('SC18', variant).run()
            self.assertTrue(check_expected('SC18', variant, result))
            self.assertEqual(result['metrics'].get('already_invalid_landings', 0), invalid)

    def test_restore_gate_latches_all_fact_states_and_clears_after_fresh_repair(self):
        for variant in ('V1', 'V2', 'V3', 'V4'):
            s = scenario('SC19', variant)
            s.q.clear()
            b = s.builds[s.bid]
            s.docs['d0']['deleted'] = True
            b['store'].clear()
            s.apply_fact((s.bid, ('d0', 'r0'), False, None, 100))
            s.safety()
            self.assertTrue(s.enforced('d0'))
            s.force_snapshot(s.bid, 'before_restore')
            old_sid = b['repair']
            s.restore_mirror(s.bid, {})
            s.safety()
            self.assertNotEqual(old_sid, b['repair'])
            self.assertNotIn(old_sid, s.snapshots)
            self.assertFalse(s.enforced('d0'))
            self.assertTrue(s.enforced('d7'))
            self.assertEqual(s.metrics['restore_gate_flips'], 1)
            self.assertNotIn('S1_flipback', s.failures)
            s.run()
            self.assertFalse(b['restoring'])
            self.assertTrue(s.enforced('d0'))
            # A newer fact after repair is still a failing fact-based reversal.
            s.apply_fact((s.bid, ('d0', 'r0'), True, 1, 101))
            s.safety()
            self.assertIn('S1_flipback', s.failures)
            self.assertEqual(s.metrics['fact_based_flip_backs'], 1)

    def test_all_variants_request_restore_repair_even_when_counts_match(self):
        for variant in ('V1', 'V2', 'V3', 'V4'):
            result = scenario('SC20r', variant).run()
            self.assertEqual(result['verdict'], 'PASS')
            self.assertEqual(result['metrics']['rewind_equal_counts'], 1)
            self.assertEqual(result['metrics']['snapshots_restore'], 1)
            self.assertEqual(result['metrics']['restore_repairs_completed'], 1)

    def test_SC24_regression_discards_stale_view_and_ignores_its_last_page(self):
        old = scenario('SC24', 'N-viewexp').run()
        new = scenario('SC24', 'V4').run()
        self.assertIn('S1_flipback', old['violations'])
        self.assertEqual(new['verdict'], 'PASS')
        self.assertEqual(new['metrics']['replacement_aborts_view_lifetime'], 1)
        self.assertEqual(new['metrics']['snapshots'], 2)
        self.assertEqual(new['metrics']['old_snapshot_pages_ignored'], 1)
        self.assertTrue(check_expected('SC24', 'N-viewexp', old))

    def test_replacement_deadline_is_measured_from_view_not_page_receipt(self):
        s = Simulation(variant='V4', actions=[], faults=False, measure_transients=False)
        s.q.clear()
        b = s.builds['retrieval-0']
        s.time = 10
        s.start_snapshot(b)
        sid = b['repair']
        pages = [(args[1], args[2]) for _, _, kind, args in s.q if kind == 'replacement_page']
        s.time = 99
        s.replacement_page(sid, *pages[0])
        self.assertEqual(b['repair'], sid)
        s.time = 100
        s.replacement_page(sid, *pages[1])
        self.assertNotEqual(b['repair'], sid)
        self.assertNotIn(sid, s.snapshots)
        self.assertEqual(s.metrics['replacements'], 0)
        self.assertEqual(s.snapshots[b['repair']]['issued'], 100)

    def test_replacement_expiry_fence_independently_rejects_original_entry(self):
        # Directly exercise the second guard, bypassing the first guard's timer.
        s = scenario('SC24', 'V4')
        while s.time < 12:
            s.step()
        b = s.builds[s.bid]
        sid = b['repair']
        page = next(args[2] for _, _, kind, args in s.q
                    if kind == 'replacement_page' and args[0] == sid)
        s.time = 135
        s.gc_tombstones()
        s.snapshots[sid]['received'][0] = page
        s.finish_replacement(sid)
        self.assertNotIn(sid, s.snapshots)
        self.assertNotIn((s.bid, 'd0', 'r0'), s.facts)
        self.assertEqual(s.metrics['expired_replacement_entries_rejected'], 1)
        self.assertEqual(s.metrics['snapshots_expired_replacement'], 1)
        self.assertEqual(s.snapshots[b['repair']]['issued'], 135)

    def test_silent_equal_count_drift_has_no_runbook_and_needs_digest(self):
        for variant in ('V1', 'V2', 'V3', 'V4'):
            result = scenario('SC20u', variant).run()
            self.assertTrue(check_expected('SC20u', variant, result))
            self.assertEqual(result['metrics']['silent_rewinds'], 1)
            self.assertEqual(result['metrics'].get('snapshots_restore', 0), 0)
            self.assertEqual(result['metrics'].get('restore_gate_flips', 0), 0)

    def test_pending_age_confirms_lost_write_confirmation(self):
        self.assertGreater(PENDING_MAX, 40 + 55)
        old = scenario('SC22', 'V3').run()
        new = scenario('SC22', 'V4').run()
        self.assertIn('L4', old['violations'])
        self.assertEqual(new['verdict'], 'PASS')
        self.assertGreater(new['metrics'].get('snapshots_pending_age', 0), 0)

    def test_pending_age_monitor_covers_restored_facts_without_live_timer(self):
        s = Simulation(variant='V4', actions=[], faults=False, measure_transients=False)
        b = s.builds['retrieval-0']
        b['counter'] += 1
        s.apply_fact((b['id'], ('d0', 'r0'), True, 1, b['counter']), 'pending')
        s.q.clear()
        s.time = PENDING_MAX + 1
        s.heartbeat()
        result = s.run()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(s.metrics['snapshots_pending_age'], 1)

    def test_inflight_write_confirmation_clears_fence_and_preserves_S1(self):
        s = scenario('SC23', 'V4')
        result = s.run()
        self.assertEqual(result['verdict'], 'PASS')
        self.assertEqual(result['metrics']['late_landings'], 1)
        self.assertTrue(any('register_v=8 confirm_v=10 fence=9' in line for line in s.trace))

    def test_store_failure_retry_gets_new_fact_version(self):
        s = scenario('SC15', 'V3')
        b = s.builds[s.bid]
        s.q.clear()
        s.script_read('d0', 0)
        # Inject one failed store write after the actual atomic register.
        original_write = s.write_attempt
        first = [True]
        def write(bid, attempt, failed=False):
            if first[0]:
                first[0] = False
                return original_write(bid, attempt, True)
            return original_write(bid, attempt, failed)
        s.write_attempt = write
        s.run()
        versions = [line for line in s.trace if 'register retrieval-0' in line]
        self.assertGreaterEqual(len(versions), 2)
        self.assertEqual(s.metrics['store_write_failures'], 1)
        self.assertNotEqual(versions[0].split('v=')[-1], versions[1].split('v=')[-1])

    def test_sdk_giveup_starts_snapshot(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.time = RETRY_LIFETIME
        s.outbox_send(dict(change=('retrieval-0', ('d0', 'r0'), True, 1, 1),
                           issued=0, epoch=0, snapshot=None))
        self.assertEqual(s.metrics['sdk_giveups'], 1)
        self.assertIsNotNone(s.builds['retrieval-0']['repair'])

    def test_sdk_deadline_does_not_wait_for_slow_network_packet(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.q.clear()
        s.send_report(('retrieval-0', ('d0', 'r0'), True, 1, 1))
        s.step()  # send, then hold the already-sent packet in the network
        s.q = [(180 if kind == 'report' else t, serial, kind, args)
               for t, serial, kind, args in s.q]
        heapq.heapify(s.q)
        s.step()
        self.assertEqual(s.time, RETRY_LIFETIME)
        self.assertEqual(s.metrics['sdk_giveups'], 1)
        self.assertIsNotNone(s.builds['retrieval-0']['repair'])

    def test_bound_maintenance_is_failure_not_unknown(self):
        s = Simulation(actions=[], faults=False, measure_transients=False)
        s.facts[('retrieval-0', 'd0', 'r0')]['revision'] = -1
        result = s.run(max_steps=1)
        self.assertIn('L0', result['violations'])
        self.assertIsNone(result['unknown'])

    def test_bound_external_work_is_unknown(self):
        s = Simulation(actions=[(100, 'delete', ['d0'])], faults=False, measure_transients=False)
        result = s.run(max_steps=1)
        self.assertEqual(result['verdict'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
