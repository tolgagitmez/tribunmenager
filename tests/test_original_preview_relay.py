"""Two concurrent HTTP viewers must receive changing frames from one encoder."""
import hashlib
import io
import threading
import time
import unittest
import urllib.request

from original_preview_relay import FrameHub,PreviewServer,read_jpegs

def read_frame(response):
    if response.readline()!=b'--frame\r\n':
        raise ValueError('Missing frame boundary')
    headers={}
    while True:
        line=response.readline()
        if line==b'\r\n':
            break
        if not line:
            raise ValueError('Truncated multipart headers')
        k,v=line.decode('ascii').split(':',1)
        headers[k]=v.strip()
    frame=response.read(int(headers['Content-Length']))
    if response.read(2)!=b'\r\n':
        raise ValueError('Missing frame terminator')
    return int(headers['X-Frame-Sequence']),hashlib.sha256(frame).hexdigest()


class RelayTests(unittest.TestCase):
    def test_latest_frame_and_bounded_parser(self):
        hub=FrameHub()
        a=b'\xff\xd8A\xff\xd9'
        b=b'\xff\xd8B\xff\xd9'
        read_jpegs(io.BytesIO(a+b),hub)
        self.assertEqual(hub.latest(0),(2,b))
        self.assertIsNone(hub.latest(2,.01))
        with self.assertRaises(ValueError):
            read_jpegs(io.BytesIO(a+b'broken'),hub)
        hub.close()
        self.assertFalse(hub.publish(a))
        self.assertIsNone(hub.latest(0))

    def test_two_http_viewers_share_one_producer(self):
        hub=FrameHub()
        with PreviewServer(hub,max_clients=2) as server:
            worker=threading.Thread(target=server.serve_forever,daemon=True)
            worker.start()
            url=f'http://127.0.0.1:{server.server_port}/preview.mjpeg'
            try:
                hub.publish(b'\xff\xd8A\xff\xd9')
                with urllib.request.urlopen(url,timeout=4) as a,urllib.request.urlopen(url,timeout=4) as b:
                    self.assertEqual(read_frame(a),read_frame(b))
                    hub.publish(b'\xff\xd8B\xff\xd9')
                    self.assertEqual(read_frame(a),read_frame(b))
                    hub.publish(b'\xff\xd8C\xff\xd9')
                    self.assertEqual(read_frame(a),read_frame(b))
                    self.assertEqual(hub.sequence,3)
            finally:
                hub.close()
                server.shutdown()
                worker.join(timeout=5)
