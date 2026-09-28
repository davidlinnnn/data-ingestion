import unittest
import dis
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace

import candidate_window as candidate


class CandidateWindowTest(unittest.TestCase):
    def test_group_10_contract_and_single_parser(self):
        candidate.base_config_producer = {'parse.py': 'digest'}
        profiles = {'06': {'id': 'profile', 'release': 'old'}}
        changed = candidate.candidate_profiles(profiles)
        self.assertEqual(changed['06']['group_pages'], 10)
        self.assertNotEqual(changed['06']['release'], 'old')
        groups = [dict(stage='group', parser=dict(pid=7, restarts=1, recycles=0))
                  for _ in range(16)]
        results = [dict(sid=sid, result={'steps': part}) for sid, part in zip(
            candidate.base.SEQUENCE, (groups[:3], groups[3:5], groups[5:7],
                                      groups[7:13], groups[13:]))]
        self.assertEqual(candidate.warm_checks(results),
                         {'groups': 16, 'pids': [7], 'recycles': 0})
        values = [instruction.argval for instruction in
                  dis.get_instructions(candidate.base.run_window)]
        self.assertEqual(values.count(16), 2)
        self.assertIs(candidate.base.run_window.__globals__['validate_process_evidence'],
                      candidate.validate_process_evidence)

    def test_inner_scope_is_group_10_and_single_parser(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'manifest.json'
            canonical = candidate.base.canonical(candidate.SCOPE).encode()
            digest = hashlib.sha256(canonical).hexdigest()
            path.write_text(json.dumps({
                'authorization_scope': candidate.SCOPE,
                'authorization_scope_sha256': digest,
                'identity': candidate.IDENTITY,
            }))
            candidate.validate_scope(SimpleNamespace(
                integration_manifest=path, authorization_scope_sha256=digest,
                name=candidate.IDENTITY['phase'],
                expected_run_id=candidate.IDENTITY['run_id'],
                expected_prefix=candidate.IDENTITY['prefix']))
