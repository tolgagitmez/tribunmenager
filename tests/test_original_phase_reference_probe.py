import tempfile
import unittest
from pathlib import Path
from original_phase_reference_probe import PhaseSamples,FRAME_BYTES,PRE,POST
from original_capture_probe import ACTIVE,HALF,FULL,DONE

class PhaseReferenceTests(unittest.TestCase):
    def test_capture_windows_and_unreviewed_export(self):
        s=PhaseSamples()
        data=bytes(FRAME_BYTES)
        for t,marker in ((2,ACTIVE),(8,HALF),(10,ACTIVE),(18,FULL),(20,DONE)):
            for offset in (-.9,-.5,-.25):
                s.sample(t+offset,data)
            s.mark(t,marker,marker)
            for offset in (.1,.3,.9):
                s.sample(t+offset,data)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidate'
            report=s.export(path)
            self.assertTrue(report['phaseMarkerOrderVerified'])
            self.assertFalse(report['operatorReviewed'])
            self.assertFalse(report['normalLeagueCalibrationVerified'])
            for event in report['events']:
                self.assertTrue(all(-PRE*1000<=f['receiptOffsetMs']<=POST*1000 for f in event['frames']))
                self.assertEqual(len(event['frames']),4)
                for f in event['frames']:
                    self.assertTrue((path/f['file']).read_bytes().startswith(b'P5\n1280 1024\n255\n'))

    def test_reject_truncated_frame_and_missing_markers(self):
        s=PhaseSamples()
        with self.assertRaises(ValueError):
            s.sample(0,b'bad')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((ValueError,RuntimeError)):
                s.export(Path(tmp)/'invalid')

if __name__=='__main__':
    unittest.main()
