"""Private shared-clock replay pilot. Not live simulation or public hosting."""
import hashlib
import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import threading
import time

DURATION=300.0
MAX_BYTES=256*1024*1024

class ReplayClock:
    def __init__(self,start,clock=time.monotonic):
        if not math.isfinite(start):
            raise ValueError('Invalid start time')
        self.start=start
        self.clock=clock

    def state(self):
        now=self.clock()
        elapsed=now-self.start
        return dict(serverTimeMs=now*1000,startTimeMs=self.start*1000,
                    durationSeconds=DURATION,positionSeconds=min(DURATION,max(0,elapsed)),
                    phase='waiting' if elapsed<0 else 'finished' if elapsed>=DURATION else 'playing')


class ReplayServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,path,expected_sha,start_delay=3,port=0,*,scheduled_epoch=None,fixture_key=None):
        from original_match_playback import track_timing
        if not re.fullmatch('[0-9a-f]{64}',expected_sha) or not 0<=start_delay<=60:
            raise ValueError('Invalid replay identity or start delay')
        if scheduled_epoch is not None and (type(scheduled_epoch) not in (int,float) or not math.isfinite(scheduled_epoch) or scheduled_epoch<=0):
            raise ValueError('Invalid scheduled kickoff')
        if (scheduled_epoch is None)!=(fixture_key is None) or (fixture_key is not None and not re.fullmatch('[0-9a-f]{64}',fixture_key)):
            raise ValueError('Scheduled replay requires explicit fixture identity')
        self.fixture_key=fixture_key
        self.scheduled_epoch=scheduled_epoch
        path=Path(path)
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=MAX_BYTES:
            raise ValueError('Invalid replay file')
        # Freeze the actual served bytes; the source cannot change mid-match.
        with path.open('rb') as source:
            self.media=source.read(MAX_BYTES+1)
        if len(self.media)>MAX_BYTES or hashlib.sha256(self.media).hexdigest()!=expected_sha:
            raise ValueError('Replay SHA-256 mismatch')
        import tempfile
        with tempfile.TemporaryDirectory(prefix='clock-replay-') as tmp:
            verified=Path(tmp)/'verified.mp4'
            verified.write_bytes(self.media)
            tracks=track_timing(verified)
        v,a=tracks['video'],tracks['audio']
        if (v['frames']!='9000' or v['frameRate']!='30/1' or a['sampleRate']!='48000'
                or any(abs(t['duration']-300)>.001 or abs(t['start'])>.001 for t in (v,a))):
            raise ValueError('Exact 300-second encoded A/V required')
        self.identity=expected_sha
        self.script=Path(__file__).with_name('original-shared-replay.js').read_bytes()
        self.slots=threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1',port),ReplayHandler)
        # Establish the monotonic epoch once per process from the persisted UTC
        # kickoff. Viewer requests cannot start or reset it.
        start=(time.monotonic()+start_delay if scheduled_epoch is None else
               time.monotonic()+(scheduled_epoch-time.time()))
        self.replay_clock=ReplayClock(start)

    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self,request,address):
        try:
            super().process_request_thread(request,address)
        finally:
            self.slots.release()


class ReplayHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(5)
        super().setup()

    def log_message(self,*args):
        pass

    def end_headers(self):
        self.send_header('Cache-Control','no-store')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        super().end_headers()

    def reply(self,data,kind,status=200,extra=()):
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        for key,value in extra:
            self.send_header(key,value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass

    def do_GET(self):
        if (self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}'
                or self.headers.get('Sec-Fetch-Site')=='cross-site'
                or self.headers.get('Origin') not in (None,f'http://127.0.0.1:{self.server.server_port}')):
            self.send_error(403)
            return
        if self.path=='/clock':
            state=self.server.replay_clock.state()
            state.update(replaySha256=self.server.identity,liveSimulation=False,
                         fixtureKey=self.server.fixture_key,scheduledKickoffUtc=self.server.scheduled_epoch,
                         scoreWritten=False)
            self.reply(json.dumps(state).encode(),'application/json')
        elif self.path=='/viewer':
            self.reply(b'<!doctype html><meta charset="utf-8"><title>Shared replay pilot</title><video playsinline muted preload="auto" src="/match.mp4"></video><p id="status"></p><button id="sound">Sound</button><script src="/clock.js"></script>','text/html; charset=utf-8')
        elif self.path=='/clock.js':
            self.reply(self.server.script,'text/javascript; charset=utf-8')
        elif self.path=='/match.mp4':
            data=self.server.media
            n=len(data)
            headers=[('Accept-Ranges','bytes'),('ETag','"'+self.server.identity+'"')]
            raw=self.headers.get('Range')
            if raw is None:
                self.reply(data,'video/mp4',extra=headers)
                return
            match=re.fullmatch(r'bytes=(\d{1,12})-(\d{0,12})',raw)
            if not match or int(match[1])>=n or (match[2] and int(match[2])<int(match[1])):
                self.reply(b'','video/mp4',416,headers+[('Content-Range',f'bytes */{n}')])
                return
            start=int(match[1])
            end=min(n-1,int(match[2])) if match[2] else n-1
            self.reply(memoryview(data)[start:end+1],'video/mp4',206,headers+[('Content-Range',f'bytes {start}-{end}/{n}')])
        else:
            self.send_error(404)
