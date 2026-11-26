import importlib.util,json,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
from native_video_control import ControlBridge
spec=importlib.util.spec_from_file_location("hls",HERE/"native-live-video.py")
hls=importlib.util.module_from_spec(spec);spec.loader.exec_module(hls)
def frame(seq=1):
    return dict(schema=1,engine="league-soccer",done=False,elapsedMs=seq*100,matchMs=seq*1800,score=[0,0],
        inPlay=True,setPiece=False,humanGamers=[0,0],players=[{"team":t} for t in (0,1) for _ in range(11)],
        managerTactics=[{"team":0,"revision":0},{"team":1,"revision":0}])
class ControlTest(unittest.TestCase):
    def test_capability_scope_and_native_ack(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);media=p/"hls";media.mkdir();trace=p/"trace"
            c=ControlBridge({},p/"commands",trace)
            c.session.ingest(frame())
            s=hls.make_server(media,"spectator",{"phase":"streaming"},c)
            t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
            try:
                base=f"http://127.0.0.1:{s.server_port}"
                vals=dict(press=75,counter=50,support=50,width=65,tempo=80,formation=442)
                body=dict(round=0,requestId="request-1",tactics=vals)
                def post(key,data=body,origin=base):
                    return json.load(urllib.request.urlopen(urllib.request.Request(base+"/"+key+"/tactics.json",data=json.dumps(data).encode(),headers={"Content-Type":"application/json","Origin":origin})))
                with self.assertRaises(urllib.error.HTTPError) as e:post("spectator")
                self.assertEqual(e.exception.code,404)
                with self.assertRaises(urllib.error.HTTPError) as e:post(c.tokens[0],origin="https://example.com")
                self.assertEqual(e.exception.code,403)
                with self.assertRaises(urllib.error.HTTPError) as e:post(c.tokens[0],{**body,"side":1})
                self.assertEqual(e.exception.code,400)
                a=post(c.tokens[0]);self.assertEqual(a["state"],"submitted-not-applied")
                self.assertEqual(a,post(c.tokens[0]));self.assertFalse((c.directory/"team-1.txt").exists())
                self.assertEqual(c.read(0)["appliedRevision"],0)
                f=frame(2);f["managerTactics"][0]=dict(team=0,revision=1,appliedMatchMs=3600,appliedElapsedMs=200,**vals)
                c.session.ingest(f);self.assertEqual(c.read(0)["appliedRevision"],1)
                self.assertEqual(c.read(1)["appliedRevision"],0)
                c.close();self.assertFalse(c.read(0)["canControl"])
            finally:s.shutdown();s.server_close();t.join()
