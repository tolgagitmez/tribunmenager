import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_texture_cache_comparison import parse_texture,compare
class TextureCacheTest(unittest.TestCase):
    def test_observed_counts(self):
        s='[tribun-texture-cache] mode=1 calls=256 changes=1000 binds=700 repeats=300\n'
        self.assertEqual(parse_texture(s,1)['bindsPerTransition'],.7)
        for raw in ('',s.replace('binds=700','binds=800'),s.replace('mode=1','mode=0'),s.replace('calls=256','calls=512')):
            with self.assertRaises(ValueError):parse_texture(raw,1)
        self.assertEqual(parse_texture(s.replace('mode=1','mode=0').replace('binds=700','binds=1000'),0)['bindsPerTransition'],1)
    def row(self,mode,rate):
        return dict(textureCache=mode,textureEvidence=dict(mode=mode,calls=256,bindsPerTransition=rate),renderSize='1280x720',shadowSize=2048,shadowEvidence=dict(width=2048,height=2048,observed=True),fixtureSha256='x',passed=True,quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=.5,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),renderProbe=dict(averageSwapsPerSecond=15,p95GapMs=80))
    def test_no_promotion(self):
        a,b=self.row(0,1),self.row(1,.7)
        r=compare([a,b]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        b['textureEvidence']=None;self.assertFalse(compare([a,b])['passed'])
