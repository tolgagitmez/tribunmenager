import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_private_prototype import check_mapping, aligned_source, require_same_run
from native_extended_capture import sha
from native_media_retime import probe, duration


def mapping():
    return dict(candidateMappingPassed=True,simulationMs=12000,anchors=[
        dict(nativeMs=0,candidatePtsUs=2000000),
        dict(nativeMs=6000,candidatePtsUs=8010000),
        dict(nativeMs=12000,candidatePtsUs=14000000)])


class PrivatePrototypeTest(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(check_mapping(mapping(),12000),(2,10000))

    def test_non_linear_drift(self):
        m=mapping()
        m['anchors'][1]['candidatePtsUs']+=100000
        with self.assertRaisesRegex(ValueError,'Nonlinear'):
            check_mapping(m,12000)

    def test_same_run_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            files=[Path(tmp)/n for n in ('trace','video','markers','alignment')]
            for i,f in enumerate(files):
                f.write_text(str(i))
            trace,video,markers,alignment=files
            m=dict(traceSha256=sha(trace),videoSha256=sha(video))
            c=dict(m,status='raw-capture-observed',rawCoveragePassed=True)
            f=dict(visualCalibrationPassed=True,audioPacketContinuity=dict(continuityPassed=True),
                   videoSha256=sha(video),markersSha256=sha(markers),alignmentSha256=sha(alignment))
            self.assertEqual(require_same_run(c,m,f,*files),(sha(trace),sha(video)))
            video.write_text('changed')
            with self.assertRaisesRegex(ValueError,'Mixed or changed'):
                require_same_run(c,m,f,*files)

    def test_real_absolute_pts_trim(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw.mp4'
            aligned=Path(tmp)/'aligned.mp4'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',
                'testsrc2=size=160x90:rate=25:duration=14',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=14',
                '-c:v','libx264','-threads','2','-c:a','aac','-output_ts_offset','2',
                str(raw)],check=True)
            aligned_source(raw,aligned,4,12000)
            v,a,m=probe(aligned)
            self.assertAlmostEqual(duration(v,m['duration']),12,delta=.08)
            self.assertAlmostEqual(duration(a,m['duration']),12,delta=.08)
            with self.assertRaisesRegex(ValueError,'do not cover'):
                aligned_source(raw,Path(tmp)/'invalid.mp4',6,12000)


if __name__=='__main__':
    unittest.main()
