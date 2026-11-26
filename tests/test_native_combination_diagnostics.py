from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_combination_diagnostics import inspect_combinations

def line(kind,event,a=7,b=8,c=7):
    return f'[tribun-combination187] team=0 kind={kind} event={event} a={a} b={b} c={c}\n'

class CombinationDiagnosticsTest(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(data)
            return inspect_combinations(p)
    def test_native_sequences(self):
        r=self.read(''.join(line('wall',e) for e in ('start','receipt','second','complete'))+
                    ''.join(line('triangle',e,c=9) for e in ('start','receipt','second','complete')))
        for kind in ('wall','triangle'):
            self.assertEqual(r['counts'][kind],dict(start=1,receipt=1,second=1,complete=1))
        self.assertEqual(r['unresolvedKeys'],0)
    def test_invalid_and_unresolved(self):
        r=self.read(line('wall','complete')+line('wall','start')+line('wall','second')+line('triangle','start'))
        self.assertEqual(r['unmatchedEvents'],2)
        self.assertEqual(r['invalidLines'],1)
        self.assertEqual(r['unresolvedKeys'],1)
    def test_cancel_and_no_evidence(self):
        r=self.read(line('wall','start')+line('wall','cancel'))
        self.assertEqual(r['counts']['wall']['cancel'],1)
        self.assertEqual(r['unresolvedKeys'],0)
        self.assertFalse(self.read('')['evidenceAvailable'])
