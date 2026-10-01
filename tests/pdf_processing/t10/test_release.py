"""Operator release seam: immutable config, bounded serial workers, checked routing."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('pdf_release', ROOT/'deploy/pdf-processing/release.py')
assert spec is not None and spec.loader is not None
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTest(unittest.TestCase):
    def test_rendered_release_is_serial_frozen_and_selected(self):
        profile = json.loads((ROOT/'deploy/pdf-processing/profiles/selected-native-v1.json').read_text())
        bundle = release.render(profile, 'example/pdf@sha256:'+'1'*64,
            'pdf-core', 't10-test', 't09a', 't10/test/',
            'temporal.pdf-t09a-validation:7233', 'http://objects.pdf-t09a-validation:9000', 'pdf-store')
        deployments = [x for x in bundle['items'] if x['kind'] == 'Deployment']
        self.assertEqual(len(deployments), 2)
        self.assertTrue(all(x['spec']['replicas'] == 0 for x in deployments))
        activity = deployments[1]['spec']['template']['spec']
        env = {x['name']: x['value'] for x in activity['containers'][0]['env']}
        self.assertEqual(env['WORKER_STAGE'], 'all')
        self.assertEqual(json.loads(env['PARSER_BUDGETS'])['max_requests'], 20)
        self.assertEqual(json.loads(env['LIMITS'])['max_pages'], 51)
        self.assertEqual(activity['containers'][0]['resources']['limits'], {'cpu': '4', 'memory': '5Gi'})
        config = bundle['items'][0]
        self.assertTrue(config['immutable'])
        route = json.loads(config['data']['route.json'])
        self.assertEqual(len(set(route['queues'].values())), 7)
        profile['content_evidence']['reviews']={'source':{'original_source':{'artifact':{'key':'old-prefix/sources/original.pdf'}}}}
        with self.assertRaisesRegex(ValueError,'original source'):
            release.render(profile,'example/pdf@sha256:'+'1'*64,'pdf-core','t10-test','t09a','t10/test/',
                'temporal:7233','http://objects:9000','pdf-store')
        profile['content_evidence']['reviews']={}
        with self.assertRaisesRegex(ValueError, 'release name'):
            release.render(profile, 'example/pdf@sha256:'+'1'*64,
                'pdf-core', 'a'*38, 't09a', 't10/test/', 'temporal:7233', 'http://objects:9000', 'pdf-store')
        profile['group_pages'] = 10
        with self.assertRaisesRegex(ValueError, 'group5'):
            release.render(profile, 'example/pdf@sha256:'+'1'*64,
                'pdf-core', 't10-test', 't09a', 't10/test/', 'temporal:7233', 'http://objects:9000', 'pdf-store')


if __name__ == '__main__':
    unittest.main()
