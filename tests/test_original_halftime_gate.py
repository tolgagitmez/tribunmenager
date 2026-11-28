import tempfile
import json
import unittest
from pathlib import Path
from original_halftime_gate import WIDTH,HEIGHT,learn_region,OnceGate,load_bundle,score

TITLE=[100,100,20,12]
BUTTON=[100,200,20,12]

def image(title,button,marker):
    result=bytearray(WIDTH*HEIGHT)
    for (x,y,w,h),value in ((TITLE,title),(BUTTON,button)):
        for dy in range(h):
            start=(y+dy)*WIDTH+x
            result[start:start+w]=bytes([value])*w
    result[-1]=marker
    return bytes(result)

class HalftimeGateTests(unittest.TestCase):
    def setUp(self):
        self.positive=[image(220,180,1),image(222,181,2)]
        self.negative=[image(0,180,3),image(220,0,4),image(0,0,5)]
        # Individual region calibration rejects each negative unless distinct
        # from both title and button. Use genuine distinct training negatives,
        # then test held-out title-only and button-only matches.
        train=[image(0,0,3),image(80,50,4),image(100,90,5)]
        self.regions=[learn_region(r,self.positive,train) for r in (TITLE,BUTTON)]

    def test_two_regions_three_consecutive_frames_once(self):
        gate=OnceGate(self.regions)
        for sample in (self.positive[0],self.positive[1],self.negative[0],
                       self.positive[0],self.negative[1],self.positive[0],self.positive[1]):
            self.assertFalse(gate.observe(sample))
        self.assertTrue(gate.observe(self.positive[0]))
        self.assertTrue(gate.fired)
        self.assertFalse(gate.observe(self.positive[1]))

    def test_reject_ambiguous_or_overlapping_regions(self):
        with self.assertRaisesRegex(ValueError,'distinguish'):
            learn_region(TITLE,self.positive,self.negative)
        with self.assertRaisesRegex(ValueError,'overlap'):
            OnceGate([self.regions[0],self.regions[0]])
        self.assertEqual(score(self.regions[0],self.negative[0]),0)

    def test_bundle_bound_to_revision_config_and_review(self):
        data=dict(revision='a'*40,configSha256='b'*64,screen=[WIDTH,HEIGHT],
                  state='halftime',operatorReviewed=True,regions=self.regions)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bundle.json'
            p.write_text(json.dumps(data))
            self.assertFalse(load_bundle(p,'a'*40,'b'*64).fired)
            with self.assertRaisesRegex(ValueError,'does not match'):
                load_bundle(p,'a'*40,'c'*64)
            p.write_text(json.dumps(dict(data,operatorReviewed=False)))
            with self.assertRaisesRegex(ValueError,'review'):
                load_bundle(p,'a'*40,'b'*64)

    def test_independent_normal_league_calibration(self):
        import hashlib
        from original_halftime_gate import league_calibration
        training=[('halftime',f) for f in self.positive]+[
            ('gameplay',image(0,0,3)),('main-menu',image(80,50,4)),('fulltime',image(100,90,5))]
        validation=[('halftime',image(221,181,6)),('halftime',image(219,179,7)),
            ('gameplay',image(5,5,8)),('main-menu',image(85,55,9)),('fulltime',image(105,95,10))]
        proof=league_calibration(self.regions,training,validation)
        self.assertTrue(proof['independentSamplesPassed'])
        self.assertFalse(proof['sourceAuthenticityVerified'])
        for bad in (validation[:-1],training,validation[:-1]+[('fulltime',image(220,180,11))]):
            with self.assertRaises(ValueError):
                league_calibration(self.regions,training,bad)
        data=dict(revision='a'*40,configSha256='b'*64,screen=[WIDTH,HEIGHT],
            state='halftime',operatorReviewed=True,regions=self.regions,
            positiveSha256=[hashlib.sha256(f).hexdigest() for s,f in training if s=='halftime'],
            negativeSha256=[hashlib.sha256(f).hexdigest() for s,f in training if s!='halftime'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'bundle.json'
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'normal league'):
                load_bundle(p,'a'*40,'b'*64,require_league=True)
            data['leagueCalibration']=proof
            p.write_text(json.dumps(data))
            self.assertFalse(load_bundle(p,'a'*40,'b'*64,require_league=True).fired)


if __name__=='__main__':
    unittest.main()
