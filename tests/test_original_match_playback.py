import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from original_match_playback import playback_plan,convert,convert_exact,exact_plan


class PlaybackTests(unittest.TestCase):
    def test_plan_never_speeds_short_recording_or_changes_simulation(self):
        self.assertEqual(playback_plan(250)['playbackSpeed'],1)
        plan=playback_plan(1500)
        self.assertEqual(plan['targetSeconds'],300)
        self.assertEqual(plan['playbackSpeed'],5)
        self.assertAlmostEqual(math.prod(plan['audioTempoFactors']),5)
        self.assertTrue(all(1<=x<=2 for x in plan['audioTempoFactors']))
        self.assertFalse(plan['live'])
        self.assertFalse(plan['nativeSimulationChanged'])
        for invalid in (0,-1,float('nan'),True):
            with self.assertRaises(ValueError):
                playback_plan(invalid)

    def test_real_ffmpeg_video_and_audio_duration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'synthetic.mp4'
            output=root/'playback.mp4'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'testsrc2=size=32x32:rate=10','-f','lavfi','-i','sine=frequency=440:sample_rate=16000',
                '-t','310','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True)
            before=source.read_bytes()
            report=convert(source,output)
            self.assertGreaterEqual(report['outputSeconds'],299.5)
            self.assertLessEqual(report['outputSeconds'],300)
            self.assertTrue(report['audioPreserved'])
            self.assertFalse(report['sourceRecordingVerifiedComplete'])
            self.assertEqual(source.read_bytes(),before)
            self.assertTrue(output.is_file())
            with self.assertRaises(ValueError):
                convert(source,output)


    def test_exact_plan_rejects_short_or_misaligned_audio(self):
        def tracks(video,audio,start=0):
            return dict(video=dict(start=0,duration=video,end=video),
                        audio=dict(start=start,duration=audio,end=start+audio))
        self.assertAlmostEqual(exact_plan(tracks(310,310))['playbackSpeed'],310/300)
        for bad in (tracks(299,299),tracks(310,299),tracks(310,310,.2),tracks(310,309.8)):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                exact_plan(bad)

    def test_exact_300_second_encoding_has_9000_frames_and_audio(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            source=root/'synthetic.mp4'
            output=root/'exact.mp4'
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'testsrc2=size=32x32:rate=10','-f','lavfi','-i','sine=frequency=440:sample_rate=16000',
                '-t','310','-c:v','libx264','-pix_fmt','yuv420p','-c:a','aac',str(source)],check=True,timeout=90)
            before=hashlib.sha256(source.read_bytes()).hexdigest()
            report=convert_exact(source,output)
            self.assertEqual(report['outputSeconds'],300)
            self.assertEqual(report['outputFrames'],9000)
            self.assertEqual(report['outputTracks']['audio']['duration'],300)
            self.assertEqual(report['sourceSha256'],before)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),before)
            self.assertEqual(report['outputSha256'],hashlib.sha256(output.read_bytes()).hexdigest())
            self.assertFalse(report['sourceRecordingVerifiedComplete'])
            self.assertFalse(report['physicalAVSyncVerified'])
            self.assertFalse(report['live'])
            with self.assertRaises(ValueError):
                convert_exact(source,output)


    def test_verified_capture_rejects_short_and_tampered_fragments(self):
        import hashlib
        from original_av_stream import encoding_args,read_playlist
        from original_match_playback import replay_verified_capture
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            archive=root/'hls'
            archive.mkdir()
            subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i',
                'testsrc2=size=64x64:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
                '-t','6',*encoding_args(archive,fmp4=True,hd=True,retain=True)],check=True,timeout=60)
            final=read_playlist(archive,fmp4=True)
            self.assertTrue(final['ended'])
            paths=sorted(archive.glob('segment-*.m4s'))
            hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
            evidence=dict(nativeFullSmokeCaptured=True,nativeMarkerOrderVerified=True,
                nativeFullStreamPlaybackVerified=True,nativeSettingsPatched=False,
                archiveFragmentCount=len(hashes),nativeMatchSpanSeconds=5,
                results=[dict(fragments=[dict(sha256=h) for h in hashes]) for _ in range(2)])
            destination=root/'candidate.mp4'
            report=replay_verified_capture(archive,hashes,evidence,destination)
            self.assertFalse(report['candidateProduced'])
            self.assertEqual(report['reason'],'native-capture-shorter-than-300-seconds')
            self.assertFalse(destination.exists())
            with self.assertRaises(ValueError):
                replay_verified_capture(archive,hashes,dict(evidence,nativeMarkerOrderVerified=False),destination)
            with self.assertRaises(ValueError):
                replay_verified_capture(archive,hashes,dict(evidence,results=[]),destination)
            paths[0].write_bytes(paths[0].read_bytes()+b'tampered')
            with self.assertRaisesRegex(ValueError,'digest mismatch'):
                replay_verified_capture(archive,hashes,evidence,destination)
            self.assertFalse(destination.exists())
