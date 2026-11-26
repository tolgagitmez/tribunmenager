import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_render_resolution import configure,verify_geometry
from native_render_resolution_comparison import compare
class ResolutionTest(unittest.TestCase):
    def test_config(self):
        s=configure('"context_x" "1280"\n"menu_smoke_match_time_scale" "1.0"\n','960x540')
        self.assertIn('"context_x" "960"',s)
        self.assertIn('"context_y" "540"',s)
        self.assertIn('"menu_smoke_match_time_scale" "1.0"',s)
        with self.assertRaises(ValueError):configure('"context_x" "1"\n"context_x" "2"','960x540')
    def test_window_geometry(self):
        self.assertTrue(verify_geometry('WIDTH=960\nHEIGHT=540\n','960x540')['verified'])
        with self.assertRaises(ValueError):verify_geometry('WIDTH=1280\nHEIGHT=720\n','960x540')
    def row(self,size,repeated,rate):
        return dict(renderSize=size,fixtureSha256='x',passed=True,quality=dict(presentation=dict(realMatchSeconds=300,repeatedReducedImageFraction=repeated,longestIdenticalImageSeconds=1,droppedFraction=0,browserCoverage=.99)),renderProbe=dict(averageSwapsPerSecond=rate,p95GapMs=80))
    def test_review_only(self):
        a,b=self.row('1280x720',.5,15),self.row('960x540',.4,20)
        result=compare([a,b]);self.assertTrue(result['candidateForFurtherReview']);self.assertFalse(result['automaticPromotion'])
        b['passed']=False;self.assertFalse(compare([a,b])['passed'])
