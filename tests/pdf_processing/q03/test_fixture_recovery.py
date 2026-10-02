"""Recovery rejects substitutions before parsing or writing private output."""
import unittest
from recover_baseline import recover


class FixtureRecovery(unittest.TestCase):
    def test_rejects_unsealed_document(self):
        with self.assertRaisesRegex(ValueError, 'historical Q03 document digest mismatch'):
            recover(b'{}')
