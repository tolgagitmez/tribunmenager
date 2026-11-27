"""HTTP transport and independent decoder evidence, not browser playback latency."""
import concurrent.futures
import hashlib
import json
import subprocess
import threading
import time
import urllib.request
from original_av_stream import read_playlist
from original_hls_relay import HLSRelay


def receive(url,names,*,fmp4):
    observed=[]
    init=last=b''
    for name in (['init.mp4',*names] if fmp4 else names):
        start=time.monotonic()
        with urllib.request.urlopen(url+'/'+name,timeout=5) as response:
            data=response.read()
            age=int(response.headers['X-Publication-Age-Ms'])
        observed.append(dict(name=name,sha256=hashlib.sha256(data).hexdigest(),
            bytes=len(data),requestMs=round((time.monotonic()-start)*1000,2),
            publicationAgeMs=age))
        if name=='init.mp4':
            init=data
        else:
            last=data
    # Decode the exact bytes each client hashed. A second HTTP fetch could
    # race segment expiry and no longer test the delivered sample.
    proc=subprocess.run(['ffmpeg','-nostdin','-v','error','-i','pipe:0',
        '-map','0:v:0','-map','0:a:0','-f','null','-'],
        input=init+last,capture_output=True,timeout=15)
    if proc.returncode:
        raise RuntimeError('AV client decoding failed: '+proc.stderr.decode(errors='replace'))
    return observed


def verify_delivery(directory,*,fmp4=False):
    report=read_playlist(directory,fmp4=fmp4)
    if len(report['segments'])<2:
        raise ValueError('At least two published segments required')
    names=[s['name'] for s in report['segments'][-2:]]
    with HLSRelay(directory,max_clients=8) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            url=f'http://127.0.0.1:{server.server_port}'
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                a,b=[pool.submit(receive,url,names,fmp4=fmp4) for _ in range(2)]
                first,second=a.result(timeout=30),b.result(timeout=30)
            if any(x['sha256']!=y['sha256'] or x['bytes']!=y['bytes'] for x,y in zip(first,second)):
                raise RuntimeError('Shared segment data differs between viewers')
            return dict(sharedAVDeliveryVerified=True,independentDecoders=2,
                sharedSegments=len(names),clients=[first,second],
                maxHttpRequestMs=max(x['requestMs'] for rows in (first,second) for x in rows),
                browserPlaybackVerified=False,captureToScreenLatencyVerified=False,
                publicStreaming=False)
        finally:
            server.shutdown()
            thread.join(timeout=5)
