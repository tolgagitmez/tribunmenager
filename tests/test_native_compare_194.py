import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_compare_194 import compare


def sample():
    return {'passed': True, 'score': [1, 0], 'quality': {'errors': {},
            'football': {'score': [1, 0], 'passes': [20, 10], 'completed': [15, 5], 'shots': [4, 3], 'onTarget': [2, 1]},
            'presentation': {'checks': {'fiveMinuteWall': True, 'fullBrowserPlayback': True}}}}


class CompareTest(unittest.TestCase):
    def test_delta(self):
        a, b = sample(), sample()
        b['quality']['football']['shots'] = [5, 4]
        b['quality']['football']['completed'] = [18, 6]
        r = compare(a, b)
        self.assertEqual(r['deltaExperimentalMinusBaseline']['shots'], 2)
        self.assertEqual(r['deltaExperimentalMinusBaseline']['passCompletionPercent'], 13.33)
        self.assertFalse(r['causalImprovementVerified'])

    def test_missing(self):
        r = compare(sample(), sample())
        self.assertIsNone(r['deltaExperimentalMinusBaseline']['controlledBoxCrossings'])
        self.assertIsNone(r['baseline']['longestIdenticalImageSeconds'])

    def test_failed(self):
        b = sample()
        b['passed'] = False
        with self.assertRaises(ValueError):
            compare(sample(), b)

    def test_invalid(self):
        b = sample()
        b['quality']['football']['completed'] = [31, 0]
        with self.assertRaises(ValueError):
            compare(sample(), b)

    def test_zero_passes(self):
        b = sample()
        b['quality']['football'].update(passes=[0, 0], completed=[0, 0])
        self.assertIsNone(compare(sample(), b)['experimental']['passCompletionPercent'])
