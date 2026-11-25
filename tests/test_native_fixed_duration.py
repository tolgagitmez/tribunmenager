import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("fixed",Path(__file__).resolve().parents[1]/"integrations/league-soccer/fixed-duration.py")
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def frames():
    return [dict(elapsedMs=5000+t,matchMs=t*18,inPlay=t<300000,done=t==300000,
        fixedClock=dict(started=True,startMs=5000,elapsedMs=t,half=t>=150000,finished=t==300000))
        for t in [0,100,149900,150000,150100,299900,300000]]
class FixedDurationTest(unittest.TestCase):
    def test_exact_boundary(self):
        self.assertEqual(f.verify(frames())["nativeElapsedMs"],300000)
    def test_no_synthetic_end(self):
        rows=frames();rows[-1]["elapsedMs"]+=100
        with self.assertRaises(ValueError):f.verify(rows)
    def test_no_missing_halftime(self):
        rows=frames();del rows[3]
        with self.assertRaises(ValueError):f.verify(rows)
    def test_no_missing_final(self):
        with self.assertRaises(ValueError):f.verify(frames()[:-1])
