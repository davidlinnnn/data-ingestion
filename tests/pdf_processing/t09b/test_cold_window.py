import asyncio
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parent))
import cold_window as cold


class ColdTest(unittest.TestCase):
    def test_serial_fresh_workers_and_failure_stops_sequence(self):
        events=[]
        class Host:
            async def stop(self): events.append('stop')
            async def start(self): events.append('start')
        class Collector:
            async def process_transition(self,name,fn): await fn()
        class Run:
            async def trial(self,sid,mode,name,previous):
                events.append(sid)
                self_outer.assertIsNone(previous)
                if sid=='08': raise RuntimeError('business failed')
                return {'sid':sid}
        self_outer=self
        with self.assertRaisesRegex(RuntimeError,'business failed'):
            asyncio.run(cold.cold_trials(Run(),Host(),Collector()))
        self.assertEqual(events,['07','stop','start','08'])
        self.assertIn(cold.Run,cold.ColdRun.__mro__)
        self.assertIs(cold.ColdRun.cancel_owned,cold.base.AttributedCandidateRun.cancel_owned)

    def test_failed_stop_never_starts_successor(self):
        events=[]
        class Host:
            async def stop(self):
                events.append('stop')
                raise RuntimeError('cleanup incomplete')
            async def start(self): events.append('start')
        class Collector:
            async def process_transition(self,name,fn): await fn()
        class Run:
            async def trial(self,sid,*args):
                events.append(sid)
                return {'sid':sid}
        with self.assertRaisesRegex(RuntimeError,'cleanup incomplete'):
            asyncio.run(cold.cold_trials(Run(),Host(),Collector()))
        self.assertEqual(events,['07','stop'])

    def test_same_parser_between_fixtures_is_rejected(self):
        def rows(pids):
            return [{'sid':sid,'result':{'pages':pages,'steps':[
                {'stage':'group','reused':False,'parser':{'pid':pid,'restarts':1,'recycles':0}}
                for _ in range((pages+4)//5)]}}
                for sid,pages,pid in zip(cold.SEQUENCE,(15,12,51),pids)]
        self.assertEqual(cold.cold_checks(rows((11,12,13)))['groups'],17)
        with self.assertRaises(Exception): cold.cold_checks(rows((11,11,11)))
