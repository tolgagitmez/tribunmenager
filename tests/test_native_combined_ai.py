import importlib.util
from pathlib import Path
import sys,unittest
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("combined",HERE/"combined-ai-benchmark.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CombinedAITest(unittest.TestCase):
    def test_isolation(self):
        run=m.I.fixed.timing.run
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),combined_ai=True)
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),combined_ai=True,keeper_ai=True)
        with self.assertRaises(ValueError):run("x","x","x",("test","1.0","0"),combined_ai=True,collective_ai=True)
    def test_gate(self):
        probes={group:{k:[1,1] for k in keys} for group,keys in m.PROBES.items()}
        rows={s:dict(deliveryPassed=True,delta={k:1 for k in m.I.METRICS},passAccuracyDelta=0,openPlayDelta=0,cpuRatio=1,pssRatio=1,candidateProbes=probes) for s in m.SCENARIOS}
        self.assertTrue(m.aggregate(rows)["diagnosticPassed"])
        rows[m.SCENARIOS[0]]["pssRatio"]=1.2
        self.assertFalse(m.aggregate(rows)["diagnosticPassed"])
        rows[m.SCENARIOS[0]]["pssRatio"]=1
        probes["triangleProbe"]["completed"]=[0,0]
        self.assertFalse(m.aggregate(rows)["diagnosticPassed"])
