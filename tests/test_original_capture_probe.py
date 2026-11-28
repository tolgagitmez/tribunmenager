import unittest
from original_capture_probe import summarize, match_intervals, ACTIVE, HALF, FULL, DONE


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

    def test_static_second_half_rejects_motion_evidence(self):
        samples=[(i/10,str(i) if i<20 else 'static') for i in range(40)]
        report=summarize(samples,[(0,1),(2,3)])
        self.assertTrue(report['halves'][0]['observedMotion'])
        self.assertFalse(report['halves'][1]['observedMotion'])
        self.assertFalse(report['evidencePassed'])
        self.assertFalse(report['deliveryQualityPassed'])

    def test_delivery_quality_is_separate_from_evidence(self):
        good=summarize([(i/30,str(i)) for i in range(120)],[(0,2),(2,4)])
        self.assertTrue(good['deliveryQualityPassed'])
        low=summarize([(i/10,str(i)) for i in range(40)],[(0,2),(2,4)])
        self.assertTrue(low['evidencePassed'])
        self.assertFalse(low['deliveryQualityPassed'])

    def test_overlapping_intervals_and_nan_rejected(self):
        for samples,intervals in [([],[(0,2),(1,3)]),([(float('nan'),'x')],[(0,2)]),
                                  ([],[(0,float('inf'))])]:
            with self.assertRaises(ValueError):
                summarize(samples,intervals)

    def test_repeated_pixels_despite_smooth_delivery(self):
        report=summarize([(i/30,'static' if i<60 else str(i)) for i in range(90)],[(0,3)])
        self.assertEqual(report['captureReceiptFps'],30)
        self.assertTrue(report['deliveryQualityPassed'])
        self.assertEqual(report['identicalTransitions'],59)
        self.assertAlmostEqual(report['longestIdenticalPixelSpanMs'],1966.7,places=1)
        self.assertEqual(report['identicalPixelRunsAtLeastOneSecond'],1)

    def test_missing_samples_do_not_extend_static_span(self):
        report=summarize([(0,'same'),(.2,'same'),(2,'same'),(2.2,'same')],[(0,3)])
        self.assertEqual(report['longestIdenticalPixelSpanMs'],200)
        self.assertAlmostEqual(report['observedIdenticalPixelSpanSeconds'],.4)
        self.assertEqual(report['identicalPixelRunsAtLeastOneSecond'],0)
        self.assertEqual(report['receiptGapsAtLeastOneSecond'],1)

    def test_half_boundary_does_not_join_static_spans(self):
        samples=[(i/10,'same') for i in range(8)]+[(2+i/10,'same') for i in range(8)]
        report=summarize(samples,[(0,.8),(2,2.8)])
        self.assertEqual(report['longestIdenticalPixelSpanMs'],700)
        self.assertEqual(report['identicalPixelRunsAtLeastOneSecond'],0)

    def test_reentered_gameplay_does_not_restart_half(self):
        markers=[ACTIVE,ACTIVE,HALF,ACTIVE,ACTIVE,FULL,DONE]
        events=[(i,marker,marker+(' Arsenal 0 - 1 Manchester United' if marker==FULL else ''))
                for i,marker in enumerate(markers)]
        intervals,score,extra=match_intervals(events)
        self.assertEqual(intervals,[(0,2),(3,5)])
        self.assertEqual(extra,2)
        self.assertTrue(score.endswith('Arsenal 0 - 1 Manchester United'))

    def test_match_parser_requires_real_halftime_and_completion(self):
        for markers in ([ACTIVE,ACTIVE,FULL,DONE],
                        [ACTIVE,HALF,FULL,DONE],
                        [ACTIVE,HALF,ACTIVE,FULL],
                        [ACTIVE,HALF,ACTIVE,HALF,FULL,DONE],
                        [ACTIVE,HALF,ACTIVE,FULL,DONE,ACTIVE]):
            with self.subTest(markers=markers),self.assertRaises(ValueError):
                match_intervals([(i,m,m) for i,m in enumerate(markers)])

    def test_invalid_intervals_and_sample_order(self):
        for samples,intervals in [([],[]),([],[(1,1)]),([(2,'a'),(1,'b')],[(0,3)])]:
            with self.assertRaises(ValueError):
                summarize(samples,intervals)


if __name__=='__main__':
    unittest.main()
