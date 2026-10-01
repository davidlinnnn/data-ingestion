"""Startup removes retained owned scratch without closing new parser admission."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'deploy/pdf-processing'))
from worker import cleanup_owned_work
import bootstrap
from pdf_processing.supervision import WarmParser


class Startup(unittest.TestCase):
    def test_inherited_memory_policy_is_applied_and_read_back(self):
        with patch('ctypes.CDLL') as load:
            load.return_value.prctl.side_effect=[0,1]
            self.assertEqual(bootstrap.memory_policy()['thp_disabled'],1)
            self.assertEqual(load.return_value.prctl.call_args_list[0].args,(41,1,0,0,0))
            self.assertEqual(load.return_value.prctl.call_args_list[1].args,(42,0,0,0,0))

    def test_startup_then_shutdown(self):
        async def check():
            with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, SCRATCH=directory):
                for name in ('preflight-stale','activity-stale','ocr-stale'):
                    Path(directory,name).mkdir()
                Path(directory,'keep.txt').write_text('other ownership')
                parser=WarmParser()
                await cleanup_owned_work(parser,'worker_startup',starting=True)
                self.assertFalse(parser.closed)
                self.assertEqual([p.name for p in Path(directory).iterdir()],['keep.txt'])
                await cleanup_owned_work(parser)
                self.assertTrue(parser.closed)
        asyncio.run(check())


if __name__=='__main__':unittest.main()
