from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_skeleton_diagnostics import inspect_skeleton

def line(snapshot=100,frame=10,anim=22,phase=1,touch=12,left='0,0,0.1',right='0.5,0,0.2'):
    return f'[tribun-skeleton-feet] snapshot={snapshot} match_ms=1800 phase={phase} player=7 anim={anim} frame={frame} touch_frame={touch} left={left} right={right} ball=0.5,0,0.1\n'

class SkeletonDiagnosticsTest(unittest.TestCase):
    def read(self,data):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log'
            p.write_text(data)
            return inspect_skeleton(p)

    def test_motion_and_contact_frame(self):
        r=self.read(line()+line(150,11,left='0.1,0,0.1')+line(200,12,left='0.2,0,0.1'))
        self.assertEqual(r['samples'],3)
        self.assertEqual(r['intervals']['leftLowAnkleMotionCandidates'],2)
        self.assertEqual(r['maxHorizontalAnkleSpeed']['left'],2.0)
        self.assertEqual(r['contactFrameSamples'],1)
        self.assertEqual(r['contactFrames'][0]['leftAnkleBallDistance'],.3)
        self.assertNotIn('rightLowAnkleIntervals',r['intervals'])

    def test_transitions_and_gaps(self):
        r=self.read(line()+line(100)+line(150,11,anim=23)+line(400,12,anim=23))
        self.assertEqual(r['duplicateSamples'],1)
        self.assertEqual(r['intervals']['excludedPairs'],2)
        self.assertIsNone(r['maxHorizontalAnkleSpeed']['left'])

    def test_missing_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(inspect_skeleton(Path(d)/'missing'))
        r=self.read(line(left='nan,0,0')+line(frame=3))
        self.assertEqual(r['invalidLines'],2)
        self.assertFalse(r['evidenceAvailable'])


    def test_leg_blend_measurements(self):
        p='[tribun-leg-blend] phase=1 match_ms=1800 player=7 actual=3.0 anim=4.0 native=0.7 adjusted=0.8\n'
        r=self.read(p+p.replace('adjusted=0.8','adjusted=0.75')+p.replace('adjusted=0.8','adjusted=1.0'))
        self.assertEqual(r['legBlendSamples'],2)
        self.assertEqual(r['maxLegBlendDelta'],.1)
        self.assertEqual(r['meanLegBlendDelta'],.075)
        self.assertEqual(r['invalidLines'],1)
        self.assertTrue(r['evidenceAvailable'])
