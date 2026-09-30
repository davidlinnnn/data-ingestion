from pathlib import Path
from types import SimpleNamespace
import unittest

from recovery_trial import Run
from recovery_window import AttributedRecoveryRun, configure_profiles, scope


class RecoveryWindowTest(unittest.TestCase):
    def test_attribution_policy_and_trial_are_composed_at_the_real_constructor(self):
        collector = SimpleNamespace(observe=lambda *args, **kwargs: None)
        run = AttributedRecoveryRun({}, {}, Path('/tmp'), None, None, None, collector=collector)
        self.assertIs(run.collector, collector)
        self.assertIs(run.trial.__func__, Run.trial)
        self.assertFalse(run.runtime_node_psi_telemetry)
        self.assertFalse(run.cancel_invoked)

    def test_candidate_grouping_only_changes_native_profile(self):
        profile = {'id': 'native', 'group_pages': 5, 'release': 'old'}
        config = {'profiles': {'native': profile, '06': dict(profile)}, 'producer': {}}
        configure_profiles(config, {'authorization_scope': scope(10)})
        self.assertEqual(config['profiles']['native']['group_pages'], 10)
        self.assertEqual(config['profiles']['06']['group_pages'], 5)
        self.assertEqual(profile['group_pages'], 5)
        self.assertNotEqual(config['profiles']['native']['release'], 'old')
