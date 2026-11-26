from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_action_diagnostics import inspect_actions

def line(event,action,actual=100):
    return f'[tribun-action] phase=1 actual_ms={actual} match_ms=1800 team=0 player=7 event={event} action={action}\n'

class ActionDiagnosticsTest(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(data)
            return inspect_actions(p)

    def test_candidates_and_contacts_separate(self):
        r=self.read(line('rejected','short-pass')+line('accepted','short-pass')+
                    line('contact','short-pass',300)+line('accepted','movement'))
        self.assertEqual(r['counts']['short-pass'],dict(rejected=1,accepted=1,contact=1))
        self.assertEqual(r['counts']['movement'],dict(accepted=1))
        self.assertEqual(r['events'][2]['actualMs'],300)

    def test_missed_and_invalid(self):
        r=self.read(line('missed-touch','shot')+line('contact','movement')+
                    '[tribun-action] bad\nunrelated\n')
        self.assertEqual(r['counts']['shot'],{'missed-touch':1})
        self.assertEqual(r['invalidLines'],2)

    def test_missing_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(inspect_actions(Path(d)/'missing'))
        self.assertFalse(self.read('ordinary log\n')['evidenceAvailable'])

    def test_bounded_events(self):
        with patch('native_action_diagnostics.MAX_EVENTS',2):
            r=self.read(line('accepted','ball-control')*3)
        self.assertEqual(r['observedEvents'],3)
        self.assertEqual(len(r['events']),2)
        self.assertTrue(r['truncated'])

    def test_size_limit(self):
        with patch('native_action_diagnostics.LIMIT',1):
            with self.assertRaises(ValueError):
                self.read('too big')
