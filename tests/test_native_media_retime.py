import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_media_retime import atempo_chain, validate_plan, render


def plan():
    return dict(schema=1,simulationMs=12000,targetPlaybackMs=3000,
                plannedPlaybackMs=3000,targetFeasible=True,segments=[
        dict(sourceStartMs=0,sourceEndMs=6000,playbackStartMs=0,playbackEndMs=1000,
             speed=6,level='routine'),
        dict(sourceStartMs=6000,sourceEndMs=7000,playbackStartMs=1000,playbackEndMs=2000,
             speed=1,level='critical'),
        dict(sourceStartMs=7000,sourceEndMs=12000,playbackStartMs=2000,playbackEndMs=3000,
             speed=5,level='routine')])


class MediaRetimeTest(unittest.TestCase):
    def test_tempo_factors(self):
        for rate in (1,1.5,2,4,6,12):
            factors=[float(s.split('=')[1]) for s in atempo_chain(rate).split(',')]
            product=1
            for factor in factors:
                self.assertGreaterEqual(factor,1)
                self.assertLessEqual(factor,2)
                product*=factor
            self.assertAlmostEqual(product,rate,places=8)

    def test_exact_frame_count(self):
        rows=validate_plan(plan(),12000,3000)
        self.assertEqual(sum(row[3] for row in rows),90)
        self.assertEqual(rows[1][2],1)

    def test_reject_critical_acceleration(self):
        p=plan()
        p['segments'][0]['level']='critical'
        with self.assertRaises(ValueError):
            validate_plan(p,12000,3000)

    def test_reject_missing_source(self):
        p=plan()
        p['segments'][1]['sourceStartMs']=6001
        with self.assertRaises(ValueError):
            validate_plan(p,12000,3000)

    def test_reject_infeasible_plan(self):
        p=plan()
        p['targetFeasible']=False
        with self.assertRaises(ValueError):
            validate_plan(p,12000,3000)

    def test_actual_ffmpeg_video_and_audio(self):
        # Generated audiovisual fixture, not native match footage.
        self.assertIsNotNone(shutil.which('ffmpeg'))
        self.assertIsNotNone(shutil.which('ffprobe'))
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.mp4'
            output=Path(d)/'output.mp4'
            subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y',
                '-f','lavfi','-i','testsrc2=size=160x90:rate=30:duration=12',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=12',
                '-c:v','libx264','-threads','2','-pix_fmt','yuv420p',
                '-c:a','aac','-shortest',str(source)],check=True)
            report=render(source,plan(),output,source_ms=12000,target_ms=3000)
            self.assertTrue(output.is_file())
            self.assertLessEqual(report['durationDifferenceMs'],80)
            self.assertAlmostEqual(report['videoSeconds'],3,delta=.08)
            self.assertAlmostEqual(report['audioSeconds'],3,delta=.08)
            info=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames',
                '-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','json',str(output)]))
            self.assertEqual(int(info['streams'][0]['nb_read_frames']),90)
            subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(output),'-f','null','-'],check=True)


if __name__=='__main__':
    unittest.main()
