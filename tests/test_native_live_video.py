import importlib.util,sys,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location("nativehls",HERE/"native-live-video.py")
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class LiveVideoTest(unittest.TestCase):
    def test_loopback_scope_and_whitelist(self):
        with tempfile.TemporaryDirectory() as d:
            media=Path(d);(media/"live.m3u8").write_text("#EXTM3U\n")
            s=m.make_server(media,"test-token",{"phase":"starting"})
            t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
            try:
                url=f"http://127.0.0.1:{s.server_port}"
                self.assertEqual(urllib.request.urlopen(url+"/test-token/live.m3u8").read(),b"#EXTM3U\n")
                for path in ("/bad/live.m3u8","/test-token/../runner.log","/test-token/%2e%2e%2frunner.log","/test-token/secret.txt"):
                    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(url+path)
                    self.assertEqual(e.exception.code,404)
            finally:s.shutdown();s.server_close();t.join()
    def test_complete_playlist(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);(p/"init.mp4").write_bytes(b"init");(p/"segment-00000.m4s").write_bytes(b"segment")
            (p/"live.m3u8").write_text('#EXTM3U\n#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2,\nsegment-00000.m4s\n#EXT-X-ENDLIST\n')
            self.assertEqual(m.validate_playlist(p)["segmentCount"],1)
            (p/"segment-00000.m4s").unlink()
            with self.assertRaises(ValueError):m.validate_playlist(p)
