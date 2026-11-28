"""Bounded, local-only single-producer JPEG preview relay.

Each viewer consumes the latest encoded frame; slow clients cannot block
the producer or grow a backlog. This is a test transport, not public streaming.
"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
import time

MAX_FRAME_BYTES=2*1024*1024

class FrameHub:
    def __init__(self):
        self.cv=threading.Condition()
        self.sequence=0
        self.frame=None
        self.closed=False

    def publish(self,frame):
        if not isinstance(frame,bytes) or not 4<=len(frame)<=MAX_FRAME_BYTES or not frame.startswith(b'\xff\xd8') or not frame.endswith(b'\xff\xd9'):
            raise ValueError('Invalid bounded JPEG frame')
        with self.cv:
            if self.closed:
                return False
            self.sequence+=1
            self.frame=frame
            self.cv.notify_all()
            return True

    def latest(self,after,timeout=3):
        with self.cv:
            self.cv.wait_for(lambda:self.closed or self.sequence>after,timeout)
            if self.closed or self.sequence<=after:
                return None
            return self.sequence,self.frame

    def close(self):
        with self.cv:
            self.closed=True
            self.cv.notify_all()


class PreviewServer(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=8
    def __init__(self,hub,port=0,max_clients=4):
        if not 1<=max_clients<=16:
            raise ValueError('Invalid viewer limit')
        self.hub=hub
        self.slots=threading.BoundedSemaphore(max_clients)
        super().__init__(('127.0.0.1',port),PreviewHandler)

    def process_request(self,request,client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request,client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self,request,client_address):
        try:
            super().process_request_thread(request,client_address)
        finally:
            self.slots.release()


class PreviewHandler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.0'
    def setup(self):
        self.request.settimeout(3)
        super().setup()

    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') is not None or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.send_error(403)
            return
        if self.path!='/preview.mjpeg':
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.end_headers()
        last=0
        deadline=time.monotonic()+1800
        try:
            while time.monotonic()<deadline:
                item=self.server.hub.latest(last)
                if item is None:
                    break
                last,jpeg=item
                header=f'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: {len(jpeg)}\r\nX-Frame-Sequence: {last}\r\n\r\n'.encode('ascii')
                self.wfile.write(header+jpeg+b'\r\n')
        except (OSError,TimeoutError):
            pass


def read_jpegs(pipe,hub):
    """Parse bounded FFmpeg image2pipe MJPEG output. No disk recording."""
    pending=bytearray()
    while True:
        data=pipe.read(4096)
        if not data:
            break
        pending.extend(data)
        while pending:
            if not pending.startswith(b'\xff\xd8'):
                if pending==b'\xff':
                    break
                raise ValueError('Invalid MJPEG start marker')
            end=pending.find(b'\xff\xd9',2)
            if end<0:
                break
            frame=bytes(pending[:end+2])
            del pending[:end+2]
            if not hub.publish(frame):
                return
        if len(pending)>MAX_FRAME_BYTES:
            raise ValueError('MJPEG frame exceeds bound')
    if pending:
        raise ValueError('Incomplete MJPEG frame')
