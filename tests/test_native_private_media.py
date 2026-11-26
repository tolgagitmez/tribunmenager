import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import native_private_media as m
from native_av_gateway import GatewayError
class MediaTest(unittest.TestCase):
    def test_allowlist_and_private_paths(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/('a'*32)/'run'/'hls';p.mkdir(parents=True)
            (p/'init.mp4').write_bytes(b'video')
            self.assertEqual(m.media_file(t,'a'*32,'init.mp4'),('video/mp4',b'video'))
            for name in ('../local-url.txt','league-gateway.key','segment-1.m4s','native-match.mp4'):
                with self.assertRaises(GatewayError):m.media_file(t,'a'*32,name)
            (p/'segment-00001.m4s').symlink_to(p/'init.mp4')
            with self.assertRaises(GatewayError):m.media_file(t,'a'*32,'segment-00001.m4s')
    def test_loopback_opt_in(self):
        h=SimpleNamespace(server=SimpleNamespace(server_address=('127.0.0.1',8000),server_port=8000),client_address=('127.0.0.1',12345),headers={'Host':'localhost:8000'})
        with patch.dict(os.environ,{'TRIBUN_NATIVE_PRIVATE_SCREEN':'0'}):self.assertFalse(m.local_allowed(h))
        with patch.dict(os.environ,{'TRIBUN_NATIVE_PRIVATE_SCREEN':'1'}):
            self.assertTrue(m.local_allowed(h))
            h.headers['X-Forwarded-For']='10.0.0.1'
            self.assertFalse(m.local_allowed(h))
            del h.headers['X-Forwarded-For']
            h.server.server_address=('0.0.0.0',8000)
            self.assertFalse(m.local_allowed(h))
