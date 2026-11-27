import tempfile
from pathlib import Path
import subprocess
import unittest
from original_av_stream import encoding_args,read_playlist,segment_probe,publication_age_ms


class AudioVideoStreamTests(unittest.TestCase):
    def test_real_av_mux_and_bounded_rolling_playlist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(['ffmpeg','-nostdin','-v','error',
                '-f','lavfi','-i','testsrc2=size=160x128:rate=25',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                '-t','16',*encoding_args(root)],check=True,timeout=60)
            report=read_playlist(root)
            self.assertEqual(len(report['segments']),6)
            self.assertEqual(report['mediaSequence'],2)
            self.assertLessEqual(report['windowSeconds'],12.1)
            self.assertTrue(report['ended'])
            for segment in report['segments']:
                path=root/segment['name']
                data=segment_probe(path)
                self.assertGreater(data['bytes'],0)
                self.assertEqual(data['audio']['sample_rate'],'48000')
                self.assertGreaterEqual(publication_age_ms(path),0)
            self.assertLessEqual(len(list(root.glob('*.ts'))),8)
            from original_hls_delivery_probe import verify_delivery
            delivery=verify_delivery(root)
            self.assertTrue(delivery['sharedAVDeliveryVerified'])
            self.assertEqual(delivery['independentDecoders'],2)
            self.assertFalse(delivery['browserPlaybackVerified'])
            self.assertFalse(delivery['captureToScreenLatencyVerified'])


    def test_playlist_rejects_remote_or_traversal_uri(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'stream.m3u8'
            path.write_text('#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:0\n#EXTINF:2,\n../segment-000000.ts\n')
            with self.assertRaises(ValueError):
                read_playlist(path)


    def test_hls_http_rejects_nonmedia_and_symlinks(self):
        import threading
        import urllib.request
        from urllib.error import HTTPError
        from original_hls_relay import HLSRelay
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'secret.txt').write_text('not media')
            (root/'segment-000000.ts').symlink_to(root/'secret.txt')
            with HLSRelay(root) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                url=f'http://127.0.0.1:{server.server_port}'
                try:
                    for name in ('secret.txt','segment-000000.ts','../secret.txt'):
                        with self.assertRaises(HTTPError) as err:
                            urllib.request.urlopen(url+'/'+name,timeout=3)
                        self.assertEqual(err.exception.code,404)
                    req=urllib.request.Request(url+'/stream.m3u8',headers={'Origin':'https://example.org'})
                    with self.assertRaises(HTTPError) as err:
                        urllib.request.urlopen(req,timeout=3)
                    self.assertEqual(err.exception.code,403)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
