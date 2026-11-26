"""Real two-private-Pulse servers, simultaneous clients, no game assets."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from native_audio_capture import private_audio

def run(root):
    barrier=Barrier(2,timeout=30)
    def session(i):
        out=root/str(i);out.mkdir()
        with private_audio(out) as env:
            barrier.wait()
            result=subprocess.run(['pactl','info'],env=env,capture_output=True,text=True,check=True,timeout=5)
            if 'Default Sink: tribun_match' not in result.stdout:raise ValueError('Wrong sink')
            # Concurrent separate clients; synthetic audio never enters a match.
            p=subprocess.Popen(['paplay','--raw','--rate=48000','--channels=1','--format=s16le','/dev/zero'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                import time
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    sinks=subprocess.check_output(['pactl','list','short','sink-inputs'],env=env,text=True,timeout=3)
                    if sinks.strip():break
                    time.sleep(.1)
                else:raise ValueError('No playback input')
                barrier.wait()
                if len(sinks.strip().splitlines())!=1:raise ValueError('Unexpected shared sink input')
                return env['PULSE_SERVER']
            finally:
                p.terminate();p.wait(timeout=5)
    with ThreadPoolExecutor(2) as pool:
        addresses=list(pool.map(session,range(2)))
    if len(set(addresses))!=2:raise ValueError('Shared socket')
    return {'passed':True,'privateServers':2,'scope':'Synthetic clients only; original OpenAL and match capture not verified'}

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as d:print(json.dumps(run(Path(d))))
