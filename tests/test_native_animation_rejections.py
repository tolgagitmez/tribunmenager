import sys
from pathlib import Path
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_animation_rejections import inspect_rejections, REASONS

def record(result='rejected', reason='requeue-momentum', req='2.5', out='0.2', phase=2, player=20):
    return f'[tribun-anim210] team=1 player={player} phase={phase} actual_ms=240000 match_ms=4200000 action=movement result={result} reason={reason} interrupt=1 requested={req} current=0.1 outgoing={out} frame=12\n'

class SelectorDiagnosticTest(unittest.TestCase):
    def parse(self, content):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'game.log';p.write_text(content)
            return inspect_rejections(p)
    def test_all_reasons(self):
        r=self.parse(''.join(record(reason=k) for k in REASONS))
        self.assertEqual(r['observedEvents'],17)
        self.assertEqual(set(r['rejectionReasons']), REASONS)
        self.assertEqual(r['invalidLines'],0)
    def test_accepted_slow_output(self):
        r=self.parse(record('accepted','selected')+record('accepted','selected',out='2.5')+record('accepted','selected',req='0'))
        self.assertEqual(r['acceptedRequestedMoveButSlowOutgoing'],1)
        self.assertEqual(r['counts'],{'movement:accepted':3})
    def test_invalid(self):
        r=self.parse(record(reason='unknown')+record(req='nan')+record(out='-1')+record('accepted','requeue-momentum')+record(phase=0)+'[tribun-anim210] malformed\n')
        self.assertEqual(r['invalidLines'],6)
        self.assertFalse(r['evidenceAvailable'])
    def test_phase_groups(self):
        r=self.parse(record()+record(phase=1)+record(player=21))
        self.assertEqual(set(r['byPlayerPhase']),{'1:20:2','1:20:1','1:21:2'})
    def test_missing_and_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(inspect_rejections(Path(tmp)/'missing'))
        r=self.parse('[tribun-action] old\n')
        self.assertEqual(r['observedEvents'],0)
        self.assertFalse(r['evidenceAvailable'])
