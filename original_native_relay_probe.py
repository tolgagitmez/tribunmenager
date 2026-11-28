"""Real native MJPEG fanout probe, only on a private disposable Xvfb.

One encoder, two independent loopback HTTP consumers. Upstream smoke config
is for test only; no default native settings or persistent saves are changed.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import original_engine as engine
from original_native_saves_probe import populate
from original_native_browser_probe import terminate,ACTIVE
from original_preview_relay import FrameHub,PreviewServer,read_jpegs


def viewer(url):
    frames={}
    with urllib.request.urlopen(url,timeout=5) as response:
        for _ in range(20):
            if response.readline()!=b'--frame\r\n':
                raise ValueError('Missing multipart boundary')
            headers={}
            for _ in range(8):
                line=response.readline()
                if line==b'\r\n':
                    break
                k,v=line.decode('ascii').split(':',1)
                headers[k]=v.strip()
            else:
                raise ValueError('Too many frame headers')
            n=int(headers['Content-Length'])
            if not 4<=n<=2*1024*1024:
                raise ValueError('Invalid frame size')
            image=response.read(n)
            if len(image)!=n or response.read(2)!=b'\r\n':
                raise ValueError('Truncated frame')
            seq=int(headers['X-Frame-Sequence'])
            if frames and seq<=max(frames):
                raise ValueError('Nonmonotonic frame sequence')
            frames[seq]=hashlib.sha256(image).hexdigest()
    return frames


def run():
    env=engine.clean_env(os.environ)
    display=env.get('DISPLAY','')
    if not display.startswith(':') or not display[1:].split('.')[0].isdigit():
        raise RuntimeError('Private Xvfb required')
    work=engine.cache_root()/engine.REVISION
    build=engine.verify_install(work,env)
    hub=FrameHub()
    with tempfile.TemporaryDirectory(prefix='native-fanout-') as tmp:
        session=Path(tmp)/'session'
        populate(build,session)
        engine.check_config(work/'source',session)
        game=capture=None
        worker=None
        errors=[]
        with tempfile.TemporaryFile() as log,tempfile.TemporaryFile() as capture_log:
            try:
                game=subprocess.Popen(['stdbuf','-oL','-eL',str(session/'gameplayfootball'),
                    str(work/'source/data/menu_smoke_full_match.config')],cwd=session,env=env,
                    stdout=log,stderr=subprocess.STDOUT)
                deadline=time.monotonic()+120
                while time.monotonic()<deadline and game.poll() is None:
                    log.seek(0)
                    if ACTIVE.encode() in log.read():
                        break
                    time.sleep(.2)
                else:
                    raise RuntimeError('Real native match did not become active')
                capture=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-f','x11grab',
                    '-draw_mouse','0','-framerate','10','-video_size','1280x1024','-i',display,
                    '-vf','scale=640:512:flags=fast_bilinear','-threads','1','-c:v','mjpeg',
                    '-q:v','5','-f','image2pipe','pipe:1'],env=env,stdout=subprocess.PIPE,stderr=capture_log)
                def produce():
                    try:
                        read_jpegs(capture.stdout,hub)
                    except Exception as exc:
                        errors.append(str(exc))
                        hub.close()
                worker=threading.Thread(target=produce,daemon=True)
                worker.start()
                if hub.latest(0,10) is None:
                    raise RuntimeError('No genuine native capture frames')
                with PreviewServer(hub,max_clients=2) as server:
                    http=threading.Thread(target=server.serve_forever,daemon=True)
                    http.start()
                    try:
                        url=f'http://127.0.0.1:{server.server_port}/preview.mjpeg'
                        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                            a=pool.submit(viewer,url)
                            b=pool.submit(viewer,url)
                            first,second=a.result(timeout=25),b.result(timeout=25)
                        shared=set(first)&set(second)
                        if len(shared)<5 or any(first[k]!=second[k] for k in shared) or min(len(set(first.values())),len(set(second.values())))<3:
                            raise RuntimeError('Viewers did not receive matching changing native frames')
                        if errors or game.poll() is not None:
                            raise RuntimeError('Native capture stopped unexpectedly')
                        print(json.dumps(dict(nativeMultiViewerRelayVerified=True,viewers=2,
                            encoders=1,framesPerViewer=[len(first),len(second)],
                            commonFrameSequences=len(shared),matchingSharedFrames=True,
                            uniqueFrameHashes=[len(set(first.values())),len(set(second.values()))],
                            transport='local MJPEG',audio=False,publicStreaming=False,
                            acceleratedUpstreamSmoke=True,fullMatchVerified=False,
                            nativeSettingsPatched=False)),flush=True)
                    finally:
                        hub.close()
                        server.shutdown()
                        http.join(timeout=5)
            except Exception:
                log.seek(0)
                print(log.read()[-5000:].decode(errors='replace'),file=sys.stderr)
                capture_log.seek(0)
                print(capture_log.read()[-2000:].decode(errors='replace'),file=sys.stderr)
                raise
            finally:
                hub.close()
                terminate(capture)
                terminate(game)
                if worker is not None:
                    worker.join(timeout=5)
    engine.verify_install(work,env)


if __name__=='__main__':
    if sys.argv[1:]==['--inside-private-xvfb']:
        run()
    elif len(sys.argv)==1:
        engine.call(['xvfb-run','-a','-s','-screen 0 1280x1024x24 -nolisten tcp',
                     sys.executable,Path(__file__).resolve(),'--inside-private-xvfb'],engine.clean_env(os.environ))
    else:
        raise SystemExit('Usage: original_native_relay_probe.py')
