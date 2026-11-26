import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_render_suite import assess_individual,assess_combined
class SuiteTest(unittest.TestCase):
    def row(self,m,costs=(1,.9,1),rate=15,repeat=.5):
        return dict(renderSuite=True,passed=True,fixtureSha256='f',renderSize='1280x720',shadowSize=2048,
            windowGeometry=dict(width=1280,height=720,requested='1280x720',verified=True),
            shadowEvidence=dict(width=2048,height=2048,observed=True),skinCache=m[0],vaoCache=m[1],textureCache=m[2],
            skinEvidence=dict(mode=m[0],sampledCalls=256,meanCallMs=costs[0]),
            vaoEvidence=dict(mode=m[1],calls=256,bindsPerEntry=costs[1]),
            textureEvidence=dict(mode=m[2],calls=256,bindsPerTransition=costs[2]),
            quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=repeat,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),
            renderProbe=dict(averageSwapsPerSecond=rate,p95GapMs=80))
    def test_selection_and_regression(self):
        base=self.row((0,0,0))
        rows=[base,self.row((1,0,0),(.9,.9,1)),self.row((0,1,0),(1,.5,1),rate=8),self.row((0,0,1),(1,.9,.8))]
        selection=assess_individual(rows)
        self.assertEqual(selection['selected'],[1,0,1])
        combined=self.row((1,0,1),(.8,.9,.8),rate=17,repeat=.45)
        result=assess_combined(rows,selection,combined,base)
        self.assertTrue(result['combinedReviewEligible'])
        self.assertFalse(result['automaticPromotion'])
        self.assertFalse(assess_combined(rows,selection,combined,self.row((0,0,0),rate=22))['combinedReviewEligible'])
        self.assertFalse(assess_combined(rows,selection,combined,None)['combinedReviewEligible'])
    def test_missing_or_mismatched_data(self):
        base=self.row((0,0,0))
        b=self.row((1,0,0),(.5,.9,1));b['fixtureSha256']='other'
        self.assertEqual(assess_individual([base,b])['selected'],[0,0,0])
        self.assertFalse(assess_individual([])['baselineValid'])

    def test_cost_must_improve_against_both_baselines(self):
        base=self.row((0,0,0))
        rows=[base,self.row((1,0,0),(.9,.9,1)),self.row((0,1,0)),self.row((0,0,1))]
        selection=assess_individual(rows)
        self.assertEqual(selection['selected'],[1,0,0])
        combined=self.row((1,0,0),(.9,.9,1),rate=17,repeat=.45)
        faster=self.row((0,0,0),(.85,.9,1))
        self.assertFalse(assess_combined(rows,selection,combined,faster)['combinedReviewEligible'])
        rows[2]['passed']=False
        self.assertFalse(assess_combined(rows,selection,combined,base)['combinedReviewEligible'])
