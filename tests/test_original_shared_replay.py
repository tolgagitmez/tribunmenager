import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from original_shared_replay import ReplayClock,ReplayServer


class SharedReplayTests(unittest.TestCase):
    def test_clock_never_depends_on_viewers(self):
        current=[99.]
        clock=ReplayClock(100.,lambda:current[0])
        for now,phase,position in ((99,'waiting',0),(100,'playing',0),
                (157,'playing',57),(400,'finished',300),(999,'finished',300)):
            current[0]=now
            state=clock.state()
            self.assertEqual(state['phase'],phase)
            self.assertEqual(state['positionSeconds'],position)
            self.assertEqual(state['startTimeMs'],100000)

    def test_private_shared_replay_late_join(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'synthetic.mp4'
            subprocess.run(['ffmpeg','-nostdin','-v','error',
                '-f','lavfi','-i','testsrc2=size=64x64:rate=30',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                '-t','300','-c:v','libx264','-threads','2','-preset','ultrafast',
                '-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(source)],
                check=True,timeout=120)
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError,'SHA-256'):
                ReplayServer(source,'0'*64)
            with ReplayServer(source,digest,start_delay=3) as server:
                worker=threading.Thread(target=server.serve_forever,daemon=True)
                worker.start()
                url=f'http://127.0.0.1:{server.server_port}'
                try:
                    with urlopen(Request(url+'/match.mp4',headers={'Range':'bytes=0-99'}),timeout=3) as response:
                        self.assertEqual(response.status,206)
                        self.assertEqual(response.read(),source.read_bytes()[:100])
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(url+'/clock',headers={'Origin':'https://other.example'}),timeout=3)
                    self.assertEqual(error.exception.code,403)
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(url+'/match.mp4',headers={'Range':'bytes=99999999999-'}),timeout=3)
                    self.assertEqual(error.exception.code,416)
                    with urlopen(url+'/clock',timeout=3) as response:
                        state=json.load(response)
                        self.assertEqual(state['replaySha256'],digest)
                        self.assertFalse(state['liveSimulation'])
                    script=Path(__file__).with_name('original-shared-replay-browser.cjs')
                    result=subprocess.run(['node',str(script),url],capture_output=True,text=True,timeout=65)
                    self.assertEqual(result.returncode,0,result.stderr)
                    report=json.loads(result.stdout)
                    self.assertTrue(report['sharedClockBrowserVerified'])
                    self.assertFalse(report['publicPlaybackVerified'])
                    report['syntheticSource']=True
                    print(json.dumps(report),flush=True)
                finally:
                    server.shutdown()
                    worker.join(timeout=5)


if __name__=='__main__':
    unittest.main()
