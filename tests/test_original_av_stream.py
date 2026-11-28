import tempfile
from pathlib import Path
import subprocess
import unittest
from original_av_stream import encoding_args,parse_playlist,read_playlist,read_segment,segment_probe,publication_age_ms


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

    def test_real_fmp4_fragments_contain_decodable_av_and_share_the_same_http_bytes(self):
        from original_hls_delivery_probe import verify_delivery
        from original_native_av_probe import audible_rms
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            subprocess.run(['ffmpeg','-nostdin','-v','error',
                '-f','lavfi','-i','testsrc2=size=160x128:rate=25',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                '-t','6',*encoding_args(root,fmp4=True)],check=True,timeout=30)
            report=read_playlist(root,fmp4=True)
            self.assertEqual(report['mediaSequence'],0)
            self.assertEqual(len(report['segments']),3)
            self.assertTrue(report['ended'])
            from original_av_stream import audit_packet_timeline
            fragments=[read_segment(root/s['name'])[0] for s in report['segments']]
            timeline=audit_packet_timeline(fragments)
            self.assertTrue(timeline['encodedTimelineVerified'],timeline)
            self.assertFalse(timeline['physicalAVSyncVerified'])
            self.assertLessEqual(timeline['maxTrackBoundaryOffsetMs'],100)
            missing=audit_packet_timeline([fragments[0],fragments[2]])
            self.assertFalse(missing['encodedTimelineVerified'])
            self.assertGreater(missing['maxPacketGapMs']['video'],1000)
            with self.assertRaises(ValueError):
                audit_packet_timeline([fragments[0],fragments[0]])
            video_starts=[]
            for segment in report['segments']:
                path=root/segment['name']
                info=segment_probe(path)
                self.assertEqual(info['bytes'],path.stat().st_size)
                self.assertEqual((info['video']['width'],info['video']['height']),(640,512))
                self.assertEqual(info['audio']['sample_rate'],'48000')
                self.assertLess(abs(info['muxAudioMinusVideoStartMs']),100)
                video_starts.append(float(info['video']['start_time']))
                self.assertGreater(audible_rms(read_segment(path)[0]),.001)
            for before,after in zip(video_starts,video_starts[1:]):
                self.assertAlmostEqual(after-before,2,places=2)
            result=verify_delivery(root,fmp4=True)
            self.assertEqual(result['sharedSegments'],2)
            self.assertEqual(result['independentDecoders'],2)
            self.assertEqual(result['clients'][0][0]['name'],'init.mp4')
            self.assertEqual([r['sha256'] for r in result['clients'][0]],
                             [r['sha256'] for r in result['clients'][1]])

    def test_fmp4_playlist_rejects_overwritten_sequences_maps_and_missing_segments(self):
        playlist=('#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:3\n#EXT-X-MAP:URI="init.mp4"\n'
                  '#EXTINF:2,\nsegment-000003.m4s\n#EXTINF:2,\nsegment-000004.m4s\n')
        for invalid in (
            playlist.replace('#EXT-X-MEDIA-SEQUENCE:3', '#EXT-X-MEDIA-SEQUENCE:0\n#EXT-X-MEDIA-SEQUENCE:3'),
            playlist.replace('#EXT-X-MAP:URI="init.mp4"', '#EXT-X-MAP:URI="other.mp4"\n#EXT-X-MAP:URI="init.mp4"'),
            playlist.replace('#EXTINF:2,', '#EXTINF:2,\n#EXTINF:2,'),
            playlist.replace('segment-000004.m4s', 'segment-000005.m4s'),
            playlist+'#EXTINF:2,\n',
        ):
            with self.subTest(playlist=invalid), self.assertRaises(ValueError):
                parse_playlist(invalid,fmp4=True)

    def test_rolling_manifest_distinguishes_expired_files_and_retained_grace_segments(self):
        import threading
        import urllib.request
        from urllib.error import HTTPError
        from original_hls_relay import HLSRelay
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'stream.m3u8').write_text('#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:3\n'
                '#EXT-X-MAP:URI="init.mp4"\n#EXTINF:2,\nsegment-000003.m4s\n')
            (root/'segment-000002.m4s').write_bytes(b'retained fragment')
            (root/'segment-000000.m4s').symlink_to(root/'nonexistent')
            with HLSRelay(root) as server:
                thread=threading.Thread(target=server.serve_forever,daemon=True)
                thread.start()
                url=f'http://127.0.0.1:{server.server_port}'
                try:
                    for name,code in [('segment-000001.m4s',410),('segment-000003.m4s',404),
                                      ('segment-000004.m4s',404),('segment-000000.m4s',404)]:
                        with self.subTest(name=name):
                            with self.assertRaises(HTTPError) as error:
                                urllib.request.urlopen(url+'/'+name,timeout=3)
                            self.assertEqual(error.exception.code,code)
                            self.assertEqual(error.exception.headers['Cache-Control'],'no-store')
                    with urllib.request.urlopen(url+'/segment-000002.m4s',timeout=3) as response:
                        self.assertEqual(response.read(),b'retained fragment')
                    (root/'segment-000002.m4s').unlink()
                    with self.assertRaises(HTTPError) as error:
                        urllib.request.urlopen(url+'/segment-000002.m4s',timeout=3)
                    self.assertEqual(error.exception.code,410)
                finally:
                    server.shutdown()
                    thread.join(timeout=5)


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
