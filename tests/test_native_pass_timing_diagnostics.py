from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_pass_timing_diagnostics import inspect_pass_timing
class PassTimingTest(unittest.TestCase):
    def test_independent_counts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            self.assertIsNone(inspect_pass_timing(p))
            p.write_text('[tribun-pass-timing] team=0 passer=7 receiver=8 match_ms=100 odds=0.8\n'
                         '[tribun-pass-timing] team=0 passer=7 receiver=8 match_ms=200 odds=0.9\n'
                         '[tribun-pass-timing-contact] team=0 passer=7 receiver=9 match_ms=300\n'
                         '[tribun-pass-timing] team=0 passer=7 receiver=8 match_ms=400 odds=nan\n')
            r=inspect_pass_timing(p)
            self.assertEqual(r['selectedRequests'],2)
            self.assertEqual(r['nativeLongPassContacts'],1)
            self.assertEqual(r['meanSelectedOdds'],.85)
            self.assertEqual(r['invalidLines'],1)
