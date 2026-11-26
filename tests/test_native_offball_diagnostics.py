from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_offball_diagnostics import inspect_offball

class OffballDiagnosticsTest(unittest.TestCase):
    def test_selection_samples(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            self.assertIsNone(inspect_offball(p))
            a='[tribun-offball188] team=0 player=7 role=primary match_ms=100 x=20 y=6 score=4\n'
            b=a.replace('player=7 role=primary','player=8 role=secondary')
            p.write_text(a+a+b+a.replace('y=6','y=nan'))
            r=inspect_offball(p)
            self.assertEqual(r['sampledSelections'],{'primary':1,'secondary':1})
            self.assertEqual(r['uniquePlayers'],2)
            self.assertEqual(r['duplicateSamples'],1)
            self.assertEqual(r['invalidLines'],1)


    def test_coordination_samples(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            a='[tribun-coordinated189] team=0 player=7 paired=1 match_ms=100\n'
            b=a.replace('paired=1','paired=0').replace('match_ms=100','match_ms=200')
            p.write_text(a+a+b+a.replace('paired=1','paired=2'))
            r=inspect_offball(p)
            self.assertEqual(r['coordinationSamples'],{'paired':1,'unpaired':1})
            self.assertEqual(r['duplicateSamples'],1)
            self.assertEqual(r['invalidLines'],1)
            self.assertTrue(r['evidenceAvailable'])
