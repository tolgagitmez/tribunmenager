from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_pressure_hold_diagnostics import inspect_pressure_hold

class PressureHoldDiagnosticsTest(unittest.TestCase):
    def read(self,events):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(''.join('[tribun-pressure-hold] team=0 carrier=7 event='+e+'\n' for e in events))
            return inspect_pressure_hold(p)
    def test_early_and_late_releases(self):
        r=self.read(['started','released','received','started','held','released','received'])
        self.assertEqual(r['counts'],{'started':2,'earlyReleased':1,'released':2,'received':2,'held':1})
        self.assertEqual(r['unresolvedKeys'],0)
    def test_invalid_order(self):
        r=self.read(['received','started','received','released','held','lost','bad'])
        self.assertEqual(r['unmatchedEvents'],3)
        self.assertEqual(r['invalidLines'],1)
        self.assertEqual(r['counts']['lost'],1)
    def test_unresolved(self):
        r=self.read(['started','held'])
        self.assertEqual(r['unresolvedKeys'],1)
        self.assertFalse(self.read([])['evidenceAvailable'])
