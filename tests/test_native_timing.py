import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location("native_timing",Path(__file__).resolve().parents[1]/"integrations/league-soccer/timing-benchmark.py")
t=importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

def frame(elapsed,play=True,set_piece=False,phase=1,done=False):
    return dict(engine="league-soccer",schema=1,elapsedMs=elapsed,matchMs=5400000 if done else 1000,
                inPlay=play,setPiece=set_piece,phaseCode=phase,done=done)

class NativeTimingTest(unittest.TestCase):
    def test_partition_and_wall_clock(self):
        s=t.Timing()
        for row,now in [(frame(0,False),1),(frame(100),2),(frame(200),2.1),
                        (frame(300,False),2.2),(frame(400,False),2.3),
                        (frame(500,False,True),2.4),(frame(600,False,True),2.5),
                        (frame(1000,False,True),3),(frame(1100,False,False,2,True),302)]:
            s.ingest(row,now)
        r=s.report()
        self.assertEqual(r["nativeElapsedMs"],1000)
        self.assertEqual(r["openPlayMs"],100)
        self.assertEqual(r["deadBallMs"],100)
        self.assertEqual(r["setPieceMs"],100)
        self.assertEqual(r["transitionMs"],300)
        self.assertEqual(r["gapMs"],400)
        self.assertEqual(r["observedWallMs"],300000)
        self.assertTrue(r["withinFiveSeconds"])
    def test_no_fake_duration(self):
        s=t.Timing()
        s.ingest(frame(0),1)
        with self.assertRaises(ValueError):s.report()
        with self.assertRaises(ValueError):s.ingest(frame(1,True,True),2)
        s.ingest(frame(300000,False,False,2,True),321)
        self.assertEqual(s.report()["deviationMs"],20000)
        self.assertFalse(s.report()["withinFiveSeconds"])
        with self.assertRaises(ValueError):s.ingest(frame(300010),322)

if __name__=="__main__":unittest.main()
