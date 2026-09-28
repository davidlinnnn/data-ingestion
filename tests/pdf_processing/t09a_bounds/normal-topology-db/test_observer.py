"""Replay the DB Python3.11 traversal race, and retain real read errors."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

if 'observer' not in globals():
    spec = importlib.util.spec_from_file_location('observer', Path(__file__).resolve().parents[2]/'q04/sentinel/node_pressure_attribution_db.py')
    observer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(observer)

class DepartingCgroup(unittest.TestCase):
    def test_directory_disappears_between_enumeration_and_descent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); gone = root/'departing'; gone.mkdir()
            live = root/'live'; live.mkdir(); (live/'memory.pressure').write_text('full total=7')
            node = root/'node'; node.write_text('full total=9')
            real = os.scandir
            def disappearing(path):
                if Path(path) == gone and gone.exists():
                    gone.rmdir()
                return real(path)
            with patch.object(observer, 'CGROUPS', root), patch.object(observer, 'NODE', node), patch('os.scandir', disappearing):
                _, total, groups = observer.snapshot()
            self.assertEqual(total, 9)
            self.assertEqual(groups, {'live': 7})

    def test_permission_failure_is_not_silenced(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); denied = root/'denied'; denied.mkdir()
            node = root/'node'; node.write_text('full total=9')
            real = os.scandir
            def failure(path):
                if Path(path) == denied:
                    raise PermissionError(13, 'permission denied', str(path))
                return real(path)
            with patch.object(observer, 'CGROUPS', root), patch.object(observer, 'NODE', node), patch('os.scandir', failure):
                with self.assertRaises(PermissionError): observer.snapshot()

if __name__ == '__main__': unittest.main()
