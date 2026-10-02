"""Fault selector pauses assembly publication, never a group document.json."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fault_worker


class Fault(unittest.TestCase):
    def test_attribution_selects_the_actual_stage(self):
        def publish(_store, operation, files, after_upload, after_register):
            after_upload({})
            return operation
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,T10_FAULT='assembly',SCRATCH=directory), \
                patch.object(fault_worker,'publish',publish), patch.object(fault_worker.threading.Event,'wait',return_value=True):
            files={'document.json':b'{}','attribution.json':json.dumps({'operation':{'kind':'group'}}).encode()}
            self.assertEqual(fault_worker.paused_publish(None,'group',files),'group')
            self.assertFalse(Path(directory,'fault.json').exists())
            files['attribution.json']=json.dumps({'operation':{'kind':'assembly'}}).encode()
            fault_worker.paused_publish(None,'assembly',files)
            self.assertEqual(json.loads(Path(directory,'fault.json').read_text())['operation'],'assembly')


if __name__=='__main__':unittest.main()
