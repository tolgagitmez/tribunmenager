"""Two independent real OpenAL sources, test tone only, private monitors."""
import array
from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import subprocess
import tempfile
from threading import Barrier
import time
from native_audio_capture import private_audio
from native_audio_ownership import probe

def power(samples,hz,rate=48000):
    w=2*math.pi*hz/rate
    real=sum(v*math.cos(w*i) for i,v in enumerate(samples))
    imag=sum(v*math.sin(w*i) for i,v in enumerate(samples))
    return (real*real+imag*imag)/max(1,len(samples)**2)

def run(root):
    exe=root/'openal-tone'
    subprocess.run(['cc','-O2',str(Path(__file__).with_name('native_openal_tone.c')),'-o',str(exe),'-lopenal','-lm'],check=True,timeout=30)
    barrier=Barrier(2,timeout=30)
    def session(i):
        out=root/str(i);out.mkdir();hz=(440,880)[i]
        with private_audio(out) as env:
            barrier.wait()
            with (out/'openal.log').open('wb') as log:
                p=subprocess.Popen([str(exe),str(hz)],env=env,stdout=log,stderr=subprocess.STDOUT)
                try:
                    deadline=time.monotonic()+6
                    while time.monotonic()<deadline:
                        if p.poll() is not None:raise RuntimeError('OpenAL source exited')
                        if probe(env,p.pid)=='owned':break
                        time.sleep(.1)
                    else:raise RuntimeError('OpenAL source ownership missing')
                    barrier.wait()
                    raw=subprocess.check_output(['ffmpeg','-nostdin','-v','error','-f','pulse','-i','tribun_match.monitor','-t','1','-ac','1','-ar','48000','-f','s16le','-'],env=env,timeout=8)
                    pcm=array.array('h',raw)
                    own=power(pcm,hz);other=power(pcm,(880,440)[i])
                    if len(pcm)<40000 or own<10000 or own<100*max(other,1):raise ValueError('OpenAL monitor tone mismatch')
                    barrier.wait()
                    return {'owned':True,'frequencyHz':hz,'ownToneDominant':True}
                finally:
                    if p.poll() is None:p.terminate()
                    try:p.wait(timeout=3)
                    except subprocess.TimeoutExpired:p.kill();p.wait()
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(session,range(2)))
    return {'passed':True,'sessions':results,'scope':'Actual OpenAL synthetic sources and isolated monitor capture; not yet full native matches'}

if __name__=='__main__':
    with tempfile.TemporaryDirectory() as d:print(json.dumps(run(Path(d))))
