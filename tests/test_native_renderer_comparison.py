import importlib.util,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("compare",HERE/"renderer-comparison.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class CaptureTest(unittest.TestCase):
    def test_environment_isolation(self):
        env=m.capture_env({"PATH":"/bin","TRIBUN_NATIVE_COMBINED_AI":"1","TRIBUN_NATIVE_NULL_RENDERER":"1","GF_CAPTURE_LIMIT":"999","SDL_VIDEODRIVER":"dummy","TRIBUN_LEAGUE_SOCCER_COMMAND_DIR":"/tmp/x"},Path("."))
        self.assertNotIn("TRIBUN_NATIVE_COMBINED_AI",env)
        self.assertNotIn("TRIBUN_NATIVE_NULL_RENDERER",env)
        self.assertNotIn("SDL_VIDEODRIVER",env)
        self.assertNotIn("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR",env)
        self.assertEqual(env["GF_CAPTURE_LIMIT"],"180")
    def test_pairing_not_menu_or_stale(self):
        def frame(minute,play=True):return dict(elapsedMs=minute*1000,matchMs=minute*60000,inPlay=play,setPiece=False,done=False,score=[0,0],players=[{}]*22)
        obs=[(i*10**9,frame(n)) for i,n in enumerate((15,45,75),1)]
        caps=[{"mtimeNs":i*10**9+10000000,"nativeImage":str(i)} for i in (1,2,3)]
        self.assertEqual(len(m.pair(caps,obs,0)),3)
        obs[1]=(2*10**9,frame(45,False))
        self.assertEqual(len(m.pair(caps,obs,0)),2)
        self.assertEqual(m.pair([{"mtimeNs":9000000000}],obs,0),[])
