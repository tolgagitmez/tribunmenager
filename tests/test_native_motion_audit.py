import importlib.util
from pathlib import Path
import unittest
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
spec=importlib.util.spec_from_file_location('motion',HERE/'native_motion_audit.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MotionTest(unittest.TestCase):
    def test_repeat_and_run(self):
        lines=['#tb 0: 1/25']+['0, %d, %d, 1, 14400, %s'%(i,i,'a' if i<20 else str(i)) for i in range(25)]
        r=m.analyze(lines)
        self.assertEqual(r['repeatedFrames'],19)
        self.assertEqual(r['identicalRunsAtLeast500ms'],1)
        self.assertAlmostEqual(r['longestIdenticalImageSeconds'],.8)
    def test_gap_not_freeze(self):
        r=m.analyze(['#tb 0: 1/25','0,0,0,1,14400,a','0,10,10,1,14400,a'])
        self.assertEqual(r['repeatedFrames'],0)
        with self.assertRaises(ValueError):m.analyze(['#tb 0: 1/25'])
