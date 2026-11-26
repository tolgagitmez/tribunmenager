import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_vao_cache_comparison import parse_vao,compare
class VaoCacheTest(unittest.TestCase):
    def test_observed_counts(self):
        s='[tribun-vao-cache] mode=1 calls=256 entries=1000 binds=700 repeats=300\n'
        self.assertEqual(parse_vao(s,1)['bindsPerEntry'],.7)
        for raw in ('',s.replace('binds=700','binds=800'),s.replace('mode=1','mode=0'),s.replace('calls=256','calls=512')):
            with self.assertRaises(ValueError):parse_vao(raw,1)
        # Baseline can redundantly bind repeated logical buffers.
        self.assertEqual(parse_vao(s.replace('mode=1','mode=0').replace('binds=700','binds=900'),0)['bindsPerEntry'],.9)
    def row(self,mode,rate):
        return dict(vaoCache=mode,vaoEvidence=dict(mode=mode,calls=256,bindsPerEntry=rate),renderSize='1280x720',shadowSize=2048,fixtureSha256='x',passed=True,quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=.5,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),renderProbe=dict(averageSwapsPerSecond=15,p95GapMs=80))
    def test_no_promotion(self):
        a,b=self.row(0,.9),self.row(1,.7)
        r=compare([a,b]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        b['vaoEvidence']=None;self.assertFalse(compare([a,b])['passed'])
