from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_extended_capture import capture_env, assess, track_diagnostics


def evidence():
    return (dict(firstEncodedObserved=10.5,kickoffObserved=11,finalObserved=14,
                 nativeSinkOwnershipVerified=True,audio=True),
            dict(encoderLaunchMonotonic=10,encoderStopRequestedMonotonic=14.2,
                 samples=[dict(nativeMs=0,observedMonotonic=11),
                          dict(nativeMs=1500,observedMonotonic=12.5),
                          dict(nativeMs=3000,observedMonotonic=14)]))


class ExtendedCaptureTest(unittest.TestCase):
    def test_isolated_environment(self):
        env=capture_env(dict(TRIBUN_NATIVE_HLS_DIR='bad',TRIBUN_GPU_DISPLAY='bad',
                             TRIBUN_NATIVE_VIDEO_CONTROL='1',LD_PRELOAD='bad',PATH='/bin'),
                        Path('match.mp4'))
        self.assertEqual(env['TRIBUN_NATIVE_EXTENDED_MATCH'],'1')
        self.assertEqual(env['TRIBUN_NATIVE_AUDIO_CAPTURE'],'1')
        self.assertEqual(env['TRIBUN_NATIVE_REALTIME'],'1')
        for k in ('TRIBUN_NATIVE_HLS_DIR','TRIBUN_GPU_DISPLAY','TRIBUN_NATIVE_VIDEO_CONTROL','LD_PRELOAD'):
            self.assertNotIn(k,env)

    def test_coverage_not_alignment(self):
        c,o=evidence()
        r=assess(c,o,4,4,3000)
        self.assertTrue(r['rawCoveragePassed'])
        self.assertFalse(r['exactMediaAlignmentVerified'])
        self.assertFalse(r['eligibleForAutomaticRetime'])
        self.assertEqual(r['maxObservedClockResidualMs'],0)

    def test_missing_audio_or_late_encoder(self):
        c,o=evidence()
        c['nativeSinkOwnershipVerified']=False
        c['firstEncodedObserved']=11.1
        r=assess(c,o,4,4,3000)
        self.assertFalse(r['rawCoveragePassed'])

    def test_short_or_mismatched_tracks(self):
        c,o=evidence()
        self.assertFalse(assess(c,o,4,2,3000)['rawCoveragePassed'])

    def test_track_start_difference_not_end_difference(self):
        r=track_diagnostics(dict(start_time='1',duration='12'),
                            dict(start_time='3',duration='10'),'13')
        self.assertEqual(r['audioMinusVideoStartMs'],2000)
        self.assertEqual(r['audioMinusVideoEndMs'],0)
        self.assertEqual(r['audioMinusVideoDurationMs'],-2000)
        self.assertEqual(r['commonCoverageSeconds'],10)

    def test_track_end_difference_not_start_difference(self):
        r=track_diagnostics(dict(start_time='1',duration='12'),
                            dict(start_time='1',duration='10'),'13')
        self.assertEqual(r['audioMinusVideoStartMs'],0)
        self.assertEqual(r['audioMinusVideoEndMs'],-2000)

    def test_invalid_track_timestamp_rejected(self):
        with self.assertRaises(ValueError):
            track_diagnostics(dict(start_time='nan',duration='12'),
                              dict(start_time='1',duration='10'),'13')

    def test_regressing_clock_rejected(self):
        c,o=evidence()
        o['samples'][2]['nativeMs']=1000
        with self.assertRaises(ValueError):
            assess(c,o,4,4,3000)


if __name__=='__main__':
    unittest.main()
