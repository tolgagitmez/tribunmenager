import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_skinning_cache_comparison import parse_skin,compare
class SkinCacheTest(unittest.TestCase):
    def test_samples(self):
        x=parse_skin('[tribun-skin-cache] mode=1 calls=256 ns=256000000\n[tribun-skin-cache] mode=1 calls=512 ns=512000000\n',1)
        self.assertEqual(x['meanCallMs'],1)
        for s in ('','[tribun-skin-cache] mode=0 calls=256 ns=1','[tribun-skin-cache] mode=1 calls=512 ns=10'):
            with self.assertRaises(ValueError):parse_skin(s,1)
    def row(self,mode,ms):
        return dict(skinCache=mode,skinEvidence=dict(mode=mode,sampledCalls=256,meanCallMs=ms),renderSize='1280x720',shadowSize=2048,shadowEvidence=dict(width=2048,height=2048,observed=True),fixtureSha256='x',passed=True,quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=.5,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),renderProbe=dict(averageSwapsPerSecond=15,p95GapMs=80))
    def test_review(self):
        a,b=self.row(0,1),self.row(1,.9)
        r=compare([a,b]);self.assertTrue(r['candidateForFurtherReview']);self.assertFalse(r['automaticPromotion'])
        b['skinEvidence']=None;self.assertFalse(compare([a,b])['passed'])
