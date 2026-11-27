"""Loopback-only bounded HLS file delivery. No upload, engine control or public binding."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import threading
import time
from original_av_stream import (SEGMENT,FMP4_SEGMENT,MAX_PLAYLIST_BYTES,MAX_SEGMENT_BYTES,
                                read_published_file,read_playlist)

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

    def end_headers(self):
        # In particular, a transient 404 must not poison a subsequent retry.
        self.send_header('Cache-Control','no-store')
        super().end_headers()

    def segment_expired(self,name):
        fragmented=FMP4_SEGMENT.fullmatch(name)
        if not fragmented and not SEGMENT.fullmatch(name):
            return False
        try:
            playlist=read_playlist(self.server.directory,fmp4=bool(fragmented))
        except ValueError:
            return False
        sequence=int(name.removeprefix('segment-').split('.',1)[0])
        return sequence<playlist['mediaSequence']

    def do_GET(self):
        if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or self.headers.get('Origin') is not None or self.headers.get('Sec-Fetch-Site')=='cross-site':
            self.send_error(403)
            return
        name=self.path[1:]
        playlist=name=='stream.m3u8'
        if name=='viewer':
            data=b'<!doctype html><meta charset="utf-8"><title>Private HLS test</title><video playsinline controls></video>'
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        fragmented=name=='init.mp4' or FMP4_SEGMENT.fullmatch(name)
        if not playlist and not fragmented and not SEGMENT.fullmatch(name):
            self.send_error(404)
            return
        limit=MAX_PLAYLIST_BYTES if playlist else MAX_SEGMENT_BYTES
        try:
            data,info=read_published_file(self.server.directory/name,limit)
        except FileNotFoundError:
            # A cached playlist can outlive the encoder's rolling window.
            # Only signal expiry once a valid newer sequence is published.
            self.send_error(410 if self.segment_expired(name) else 404)
            return
        except (OSError,ValueError):
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type','application/vnd.apple.mpegurl' if playlist else 'video/mp4' if fragmented else 'video/mp2t')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Publication-Age-Ms',str(max(0,round((time.time()-info.st_mtime)*1000))))
        self.end_headers()
        try:
            self.wfile.write(data)
        except OSError:
            pass
