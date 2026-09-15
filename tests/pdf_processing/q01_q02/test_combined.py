"""Checkpoint-only integration: corrected grouping must preserve relation delivery."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'tests/pdf_processing/q01'))
sys.path.insert(0, str(ROOT/'tests/pdf_processing/q02'))
from assemble import assemble
from fixtures import policy, SOURCE
from oracle.score import score
from pdf_processing.relationships import build, validate
from pdf_processing.compatibility import dependencies
from pdf_processing.object_store import digest

class Combined(unittest.TestCase):
    def test_corrected_assembly_retains_independently_verified_relationships(self):
        doc, _ = assemble(True)
        source = {'artifact': {'sha256': SOURCE}}
        report = build(doc, source, 'corrected-parsed', 'corrected-assembly', policy())
        self.assertEqual(len(report['resolved']), 2)
        self.assertEqual(report['unresolved'], [])
        validate(report, doc, source, 'corrected-parsed', 'corrected-assembly', policy())
        candidate = copy.deepcopy(report['candidates'])
        candidate['relationships'] = [{**r, 'disposition': 'candidate'} for r in report['resolved']]
        self.assertEqual([r['structure_pass'] for r in score(doc, candidate)][:2], [True, True])
        spec = importlib.util.spec_from_file_location("q01_runtime", ROOT/"tests/pdf_processing/q01/runtime.py")
        assert spec is not None and spec.loader is not None
        runtime = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runtime)
        runtime.verify_continuation(doc)
        with self.assertRaises(ValueError):
            validate(report, doc, source, 'old-parsed', 'old-assembly', policy())

    def test_combined_dependency_projection(self):
        from test_publication import profile
        prof = profile()
        prof["method"].update(format="PROTOTYPE-page-v1", option_types={}, model_artifacts={})
        producer = {p.name: digest(p.read_bytes()) for p in (ROOT/'src/pdf_processing').glob('*.py')}
        prof['method']['continuation'] = {'version': 'column-edge-continuation-v1', 'sha256': producer['continuation.py']}
        for helper, changed_stages, unchanged_stages in [
            ('continuation.py', ('group', 'assembly'), ()),
            ('relationship_method.py', ('evidence', 'finalize'), ('group', 'assembly'))]:
            changed = {**producer, helper: '0'*64}
            for stage in changed_stages:
                self.assertNotEqual(dependencies(stage, prof, producer), dependencies(stage, prof, changed))
            for stage in unchanged_stages:
                self.assertEqual(dependencies(stage, prof, producer), dependencies(stage, prof, changed))

if __name__ == '__main__': unittest.main()
