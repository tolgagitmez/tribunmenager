import importlib.util,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
spec=importlib.util.spec_from_file_location("nativevideo",HERE/"native-video-pilot.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class NativeVideoTest(unittest.TestCase):
    def test_isolated_environment(self):
        env=m.env_for({"PATH":"/bin","TRIBUN_NATIVE_COMBINED_AI":"1","TRIBUN_NATIVE_NULL_RENDERER":"1","TRIBUN_LEAGUE_SOCCER_COMMAND_DIR":"/tmp/x","GF_CAPTURE_DIRECTORY":"/tmp/y","SDL_VIDEODRIVER":"dummy"},Path("movie.mp4"))
        for key in ("TRIBUN_NATIVE_COMBINED_AI","TRIBUN_NATIVE_NULL_RENDERER","TRIBUN_LEAGUE_SOCCER_COMMAND_DIR","GF_CAPTURE_DIRECTORY","SDL_VIDEODRIVER"):self.assertNotIn(key,env)
        self.assertEqual(env["TRIBUN_NATIVE_FIXED_DURATION"],"1")
        self.assertEqual(env["TRIBUN_LEAGUE_SOCCER_ATTACK"],"baseline")
    def test_capture_coverage(self):
        cap=dict(firstEncodedObserved=1,kickoffObserved=2,finalObserved=302)
        v=dict(durationSeconds=305,averageEncodedPacketsPerSecond=25)
        a=m.assess(cap,v);self.assertTrue(a["captureBeforeKickoff"]);self.assertTrue(a["wallWithinOneSecond"])
        self.assertFalse(m.assess({**cap,"firstEncodedObserved":3},v)["captureBeforeKickoff"])
        self.assertFalse(m.assess(cap,{**v,"durationSeconds":20})["videoLengthAtLeastObservedMatch"])
        self.assertFalse(m.assess({},v)["captureBeforeKickoff"])
