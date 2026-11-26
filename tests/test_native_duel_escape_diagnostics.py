from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_duel_escape_diagnostics import inspect_duels

class DuelEscapeDiagnosticsTest(unittest.TestCase):
    def read(self,events):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(''.join('[tribun-duel-escape] team=0 carrier=7 defender=18 event='+e+'\n' for e in events))
            return inspect_duels(p)
    def test_outcomes(self):
        r=self.read(['started','progressed','started','lost','started','cancelled'])
        self.assertEqual(r['counts'],{'started':3,'progressed':1,'lost':1,'cancelled':1})
        self.assertEqual(r['unresolvedKeys'],0)
    def test_unmatched_and_invalid(self):
        r=self.read(['lost','started','started','unknown'])
        self.assertEqual(r['unmatchedEvents'],2)
        self.assertEqual(r['unresolvedKeys'],1)
        self.assertEqual(r['invalidLines'],1)
    def test_no_evidence(self):
        self.assertFalse(self.read([])['evidenceAvailable'])
