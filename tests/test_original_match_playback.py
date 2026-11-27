import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from original_match_playback import playback_plan,convert


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
