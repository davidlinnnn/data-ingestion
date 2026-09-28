import asyncio
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from candidate import aima_pod_window as window
import pod_preflight_n
from sentinel import run_yolo_pod_cgroup_n as runner


class AimaContractTests(unittest.TestCase):
    def setUp(self):
        self.bundle = json.loads((runner.BUNDLE / 'inputs.json').read_text())
        originals = {f['id']: {'key':runner.PREFIX+'sources/'+f['id']+'.pdf'} for f in self.bundle['fixtures']}
        self.config = {'profiles':window.q04_runtime.profiles(self.bundle, originals),
            'parser_budgets':{'startup_seconds':120,'no_progress_seconds':180,'terminate_seconds':5,'reap_seconds':5,'max_requests':20}}

    def test_original_aima_contract_and_preflight(self):
        window.validate_contract(self.config, self.bundle)
        relationship = self.config['profiles']['08']['content_evidence']['relationships']
        self.assertEqual(relationship['coverage']['mode'], 'selected_regions')
        self.assertEqual(len(relationship['coverage']['regions']), 4)
        self.assertEqual(relationship['unresolved'], 'reject')
        result = pod_preflight_n.verify_reviewed_contract(workspace=runner.REPO, bundle=runner.BUNDLE, prefix=runner.PREFIX)
        self.assertEqual(result['parser_max_requests'], 20)

    def test_yolo_budget_or_altered_aima_region_cannot_enter_runtime(self):
        changed = copy.deepcopy(self.config)
        changed['parser_budgets']['max_requests'] = 1
        with self.assertRaisesRegex(ValueError, 'original parser budget changed'):
            window.validate_contract(changed, self.bundle)
        changed = copy.deepcopy(self.config)
        changed['profiles']['08']['content_evidence']['relationships']['coverage']['regions'].pop()
        with self.assertRaisesRegex(ValueError, 'original fixture profile contract changed'):
            window.validate_contract(changed, self.bundle)

    def test_failed_final_resource_gate_never_promotes_pending_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp)
            (state/'config.json').write_text(json.dumps(self.config))
            args = SimpleNamespace(state=state,bundle=runner.BUNDLE,name=runner.PHASE)
            async def measured(args):
                root = args.state/args.name
                root.mkdir()
                window.q04_runtime.write(root/'fresh-index.json', {'08':'fresh'})
                window.q04_runtime.write(root/'phase-complete.json', {'status':'cases complete'})
                measurement = args.state/(args.name+'-measurement')
                measurement.mkdir()
                (measurement/'resource-attribution.jsonl').write_text('{}\n')
                (measurement/'resource-attribution-summary.json').write_text('{}')
            with patch.object(window, 'validate_scope'), patch.object(window, 'run_measured_window', side_effect=measured):
                with self.assertRaisesRegex(ValueError, 'all-sample resource gate failed'):
                    asyncio.run(window.run_window(args))
            root = state/args.name
            self.assertTrue((root/'fresh-index.pending.json').exists())
            self.assertFalse((root/'fresh-index.json').exists())
            self.assertFalse((root/'phase-complete.json').exists())


if __name__ == '__main__':
    unittest.main()
