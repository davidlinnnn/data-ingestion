"""Small coverage failures impractical to isolate with expensive inference."""
import unittest
from pdf_processing.enrichment import validate_coverage

class RequiredWork(unittest.TestCase):
    def test_missing_required_component_never_completes(self):
        with self.assertRaises(ValueError):
            validate_coverage(['#/pictures/0', '#/pictures/1'], [{'component':'#/pictures/0'}])

    def test_duplicate_component_cannot_substitute_for_missing_result(self):
        with self.assertRaises(ValueError):
            validate_coverage(['a', 'b'], [{'component':'a'}, {'component':'a'}])

    def test_empty_selection_is_explicitly_complete(self):
        self.assertEqual(validate_coverage([], []), 'not_applicable')
