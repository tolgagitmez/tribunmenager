import unittest
from original_capture_probe import summarize


class OriginalCaptureProbeTests(unittest.TestCase):
    def test_counts_only_active_match_intervals(self):
        samples=[(i/10,str(i)) for i in range(41)]
        report=summarize(samples,[(0.5,1.5),(2.5,3.5)])
        self.assertEqual(report['captureSamples'],20)
        self.assertEqual(report['captureReceiptFps'],10)
        self.assertEqual(report['changedFrameTransitions'],18)
        self.assertEqual(report['receiptGapsAtLeastOneSecond'],0)
        self.assertTrue(report['evidencePassed'])

    def test_static_frames_do_not_prove_motion(self):
        report=summarize([(i/10,'same') for i in range(30)],[(0,3)])
        self.assertEqual(report['captureReceiptFps'],10)
        self.assertFalse(report['hasObservedMotion'])
        self.assertFalse(report['evidencePassed'])

    def test_missing_half_evidence_rejected(self):
        report=summarize([(0.2,'a'),(0.3,'b')],[(0,1),(3,4)])
        self.assertEqual(report['halves'][1]['samples'],0)
        self.assertFalse(report['evidencePassed'])

    def test_long_gap_reported(self):
        report=summarize([(0.1,'a'),(0.3,'b'),(2.3,'c'),(2.4,'d')],[(0,3)])
        self.assertEqual(report['longestReceiptGapMs'],2000)
        self.assertEqual(report['receiptGapsAtLeastOneSecond'],1)

    def test_invalid_intervals_and_sample_order(self):
        for samples,intervals in [([],[]),([],[(1,1)]),([(2,'a'),(1,'b')],[(0,3)])]:
            with self.assertRaises(ValueError):
                summarize(samples,intervals)


if __name__=='__main__':
    unittest.main()
