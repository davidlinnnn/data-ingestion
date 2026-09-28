"""No-service checks for the joint consumer acceptance oracle."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('joint_runtime', Path(__file__).with_name('runtime.py'))
assert spec and spec.loader
joint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(joint)

class RuntimeContract(unittest.TestCase):
    def test_no_vacuous_reuse_or_ocr_pass(self):
        selection = {'selected':['picture']}
        final = {'enrichments':[{'component':'picture'}]}
        steps = [{'stage':'group','reused':False},{'stage':'assembly','reused':False},
                 {'stage':'component_ocr','component':'picture','reused':False}]
        joint.verify_work({'steps':steps}, selection, final, True)
        for changed in [[], steps[:2], [steps[0], steps[2]],
                        [dict(s,reused=True) for s in steps]]:
            with self.subTest(steps=changed), self.assertRaises(AssertionError):
                joint.verify_work({'steps':changed}, selection, final, True)
        with self.assertRaises(AssertionError):
            joint.verify_work({'steps':steps}, {'selected':[]}, {'enrichments':[]}, True)
        reused = [dict(s,reused=True) for s in steps]
        joint.verify_work({'steps':reused}, selection, final, False)

    def test_joint_oracle_rejects_old_and_corrupt_output(self):
        import sys
        sys.path.insert(0,str(ROOT/'tests/pdf_processing/q01'))
        from assemble import assemble
        from fixtures import policy, SOURCE
        from pdf_processing.relationships import build
        doc,_ = assemble(True)
        source = {'artifact':{'sha256':SOURCE}}
        report = build(doc,source,'parsed','assembly',policy())
        joint.verify_delivery(doc,report,source,'parsed','assembly',policy())
        bad = copy.deepcopy(report)
        bad['resolved'][0]['members'][0]['role']='body'
        with self.assertRaises((AssertionError,ValueError)):
            joint.verify_delivery(doc,bad,source,'parsed','assembly',policy())
        old,_ = assemble(False)
        with self.assertRaises(AssertionError):
            joint.verify_delivery(old,report,source,'parsed','assembly',policy())
