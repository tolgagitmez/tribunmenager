import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations/league-soccer"))
from native_media_audit import analyze,timeline
def track(index,offset=0,duration=.04,n=250):
    return [dict(stream_index=index,pts_time=offset+i*duration,dts_time=offset+i*duration,duration_time=duration) for i in range(n)]
def fixture(audio=True):
    s=[dict(index=0,codec_type="video",codec_name="h264",width=640,height=360)]
    p=track(0)
    if audio:
        s.append(dict(index=1,codec_type="audio",codec_name="aac",profile="LC",sample_rate="48000",channels=2))
        p+=track(1,.02,.02,500)
    return dict(streams=s,packets=p)
class MediaAuditTest(unittest.TestCase):
    def test_complete_timelines(self):
        self.assertTrue(analyze(fixture(),True,10)["timelinePassed"])
        self.assertTrue(analyze(fixture(False),False,10)["timelinePassed"])
        with self.assertRaises(ValueError):analyze(fixture(),False,10)
    def test_gap_and_dts_regression(self):
        d=fixture(False);d["packets"]=d["packets"][:100]+d["packets"][130:]
        result=analyze(d,False,8)
        self.assertFalse(result["timelinePassed"]);self.assertGreater(result["tracks"]["video"]["maxGapSeconds"],1)
        d=fixture(False);d["packets"][10],d["packets"][11]=d["packets"][11],d["packets"][10]
        self.assertFalse(analyze(d,False,10)["timelinePassed"])
    def test_av_skew_and_nonfinite(self):
        d=fixture();d["packets"]=track(0)+track(1,3,.02,500)
        self.assertFalse(analyze(d,True,10)["timelinePassed"])
        with self.assertRaises(ValueError):timeline([dict(pts_time="nan",dts_time=0,duration_time=.04)])
