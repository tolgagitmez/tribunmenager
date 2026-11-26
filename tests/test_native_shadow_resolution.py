import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_shadow_resolution_comparison import shadow_evidence,compare_shadow
class ShadowResolutionTest(unittest.TestCase):
    def test_actual_viewport(self):
        self.assertEqual(shadow_evidence('[tribun-render] shadow-viewport=1024x1024\n',1024)['width'],1024)
        for raw in ('','[tribun-render] shadow-viewport=2048x2048','[tribun-render] shadow-viewport=1024x2048'):
            with self.assertRaises(ValueError):shadow_evidence(raw,1024)
    def row(self,size,repeat,rate):
        return dict(renderSize='1280x720',shadowSize=size,shadowEvidence=dict(width=size,height=size,observed=True),fixtureSha256='x',passed=True,quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=repeat,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),renderProbe=dict(averageSwapsPerSecond=rate,p95GapMs=80))
    def test_review_only(self):
        a,b=self.row(2048,.6,12),self.row(1024,.4,16)
        r=compare_shadow([a,b]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        b['shadowEvidence']=None;self.assertFalse(compare_shadow([a,b])['passed'])
