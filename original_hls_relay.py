"""Loopback-only bounded HLS file delivery. No upload, engine control or public binding."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import os
import stat
import threading
import time
from original_av_stream import SEGMENT

MAX_SEGMENT_BYTES=16*1024*1024

class HLSRelay(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16

    def __init__(self,directory,port=0,max_clients=8):
        directory=Path(directory)
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Private HLS directory required')
        if type(max_clients) is not int or not 1<=max_clients<=32:
            raise ValueError('Invalid client limit')
        self.directory=directory.resolve()
        self.slots=threading.BoundedSemaphore(max_clients)
        super().__init__(('127.0.0.1',port),HLSHandler)

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


class HLSHandler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(4)
        super().setup()

    def log_message(self,*args):
        pass

    def do_GET(self):
        if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') is not None or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.send_error(403)
            return
        name=self.path[1:]
        playlist=name=='stream.m3u8'
        if not playlist and not SEGMENT.fullmatch(name):
            self.send_error(404)
            return
        limit=16384 if playlist else MAX_SEGMENT_BYTES
        try:
            fd=os.open(self.server.directory/name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            with os.fdopen(fd,'rb') as file:
                info=os.fstat(file.fileno())
                if not stat.S_ISREG(info.st_mode) or not 0<info.st_size<=limit:
                    raise ValueError('Invalid HLS file')
                data=file.read(limit+1)
                if len(data)!=info.st_size:
                    raise ValueError('HLS file changed')
        except (OSError,ValueError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type','application/vnd.apple.mpegurl' if playlist else 'video/mp2t')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Publication-Age-Ms',str(max(0,round((time.time()-info.st_mtime)*1000))))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass
