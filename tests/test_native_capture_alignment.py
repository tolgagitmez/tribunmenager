import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_capture_alignment import audit, candidate_pts


def rows():
    return [dict(fixedClock=dict(started=True,elapsedMs=t),
        captureClock=dict(wallUs=1002000000+t*1000,steadyUs=2000000+t*1000))
        for t in range(0,1001,100)]


class CaptureAlignmentTest(unittest.TestCase):
    def test_candidate_and_interpolation(self):
        r=audit(rows(),1000,[(1,4),(1.1,4)],1000)
        self.assertTrue(r['candidateMappingPassed'])
        self.assertAlmostEqual(candidate_pts(r,150),2.15)
        self.assertEqual(candidate_pts(r,1000),3)
        self.assertFalse(r['eligibleForAutomaticRetime'])
        self.assertFalse(r['exactMediaAlignmentVerified'])

    def test_missing_track_coverage(self):
        r=audit(rows(),1000,[(2.3,4),(1,4)],1000)
        self.assertFalse(r['candidateMappingPassed'])
        with self.assertRaises(ValueError):
            candidate_pts(r,500)

    def test_clock_jump(self):
        data=rows()
        data[-1]['captureClock']['wallUs']+=50000
        r=audit(data,1000,[(1,4),(1,4)],1000)
        self.assertFalse(r['checks']['stableWallEpoch'])

    def test_missing_samples(self):
        data=rows()
        del data[2:7]
        r=audit(data,1000,[(1,4),(1,4)],1000)
        self.assertFalse(r['checks']['nativeSampling'])
        self.assertFalse(r['checks']['wallSampling'])

    def test_reversed_clock_rejected(self):
        data=rows()
        data[2]['captureClock']['wallUs']=data[0]['captureClock']['wallUs']
        with self.assertRaises(ValueError):
            audit(data,1000,[(1,4),(1,4)],1000)

    def test_missing_final_rejected(self):
        with self.assertRaises(ValueError):
            audit(rows()[:-1],1000,[(1,4),(1,4)],1000)

if __name__=='__main__':
    unittest.main()
