import sys
from pathlib import Path
import unittest
import tempfile
HERE=Path(__file__).resolve().parents[1]/'integrations/league-soccer'
sys.path.insert(0,str(HERE))
from native_match_quality import football,presentation,inspect

class QualityTest(unittest.TestCase):
    def test_football_uses_native_counts_and_missing_telemetry(self):
        raw=dict(engine='league-soccer',score=[1,0],shots=[4,3],onTarget=[2,1],passes=[20,0],completed=[15,0],fouls=[2,1],possessionMs=[100,200],sampled=None)
        r=football(raw)
        self.assertEqual(r['totalShots'],7)
        self.assertEqual(r['passCompletionPercent'],[75,None])
        self.assertIsNone(r['totalControlledBoxCrossings'])
        raw['onTarget']=[5,1]
        with self.assertRaises(ValueError):football(raw)
    def test_presentation_flags_repetition_and_duration(self):
        n=dict(checks=dict(observedWallSeconds=300),nativeClock=dict(nativeElapsedMs=300000))
        b=dict(passed=True,ended=True,coverageFraction=.99,decodedFrames=7500,droppedFrames=10)
        m=dict(repeatedFraction=.05,longestIdenticalImageSeconds=.2)
        self.assertTrue(presentation(n,b,m)['presentationReviewEligible'])
        n['checks']['observedWallSeconds']=666
        m.update(repeatedFraction=.69,longestIdenticalImageSeconds=3.16)
        r=presentation(n,b,m)
        self.assertFalse(r['checks']['fiveMinuteWall'])
        self.assertFalse(r['checks']['reducedImageRepetitionBudget'])
    def test_missing_evidence_never_qualifies(self):
        with tempfile.TemporaryDirectory() as t:
            r=inspect(t)
            self.assertIsNone(r['football'])
            self.assertFalse(r['presentation']['presentationReviewEligible'])
            self.assertFalse(r['productionQualified'])
