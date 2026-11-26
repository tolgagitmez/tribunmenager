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


    def test_separate_stall_sources(self):
        a, b = sample(), sample()
        a['quality']['stallDiagnostics'] = {'carrier': {'complete': True, 'lastNativeMs': 300000,
            'stationaryCarrierEpisodes': 3, 'longestStationaryCarrierMs': 4200, 'excludedGapMs': 50},
            'nativeClock': {'fullTimeObserved': True, 'lastNativeMs': 300000, 'error': None,
            'wallGapCount': 1, 'longestWallGapSeconds': 4.2}}
        b['quality']['stallDiagnostics'] = {'carrier': {'complete': True, 'lastNativeMs': 300000,
            'stationaryCarrierEpisodes': 1, 'longestStationaryCarrierMs': 1500, 'excludedGapMs': 100},
            'nativeClock': {'fullTimeObserved': True, 'lastNativeMs': 300000, 'error': None,
            'wallGapCount': 0, 'longestWallGapSeconds': 0}}
        delta = compare(a, b)['deltaExperimentalMinusBaseline']
        self.assertEqual(delta['stationaryCarrierEpisodes'], -2)
        self.assertEqual(delta['longestStationaryCarrierMs'], -2700)
        self.assertEqual(delta['nativeWallGapCount'], -1)
        self.assertEqual(delta['longestNativeWallGapSeconds'], -4.2)
        self.assertEqual(delta['carrierTraceExcludedGapMs'], 50)

    def test_incomplete_stall_evidence_is_not_zero(self):
        a = sample()
        a['quality']['stallDiagnostics'] = {'carrier': {'complete': False, 'lastNativeMs': 290000,
            'stationaryCarrierEpisodes': 0}, 'nativeClock': {'fullTimeObserved': True, 'lastNativeMs': 300000,
            'error': 'ValueError', 'wallGapCount': 0}}
        result = compare(a, a)['baseline']
        self.assertIsNone(result['stationaryCarrierEpisodes'])
        self.assertIsNone(result['nativeWallGapCount'])

    def test_inconsistent_stall_count(self):
        a = sample()
        a['quality']['stallDiagnostics'] = {'carrier': {'complete': True, 'lastNativeMs': 300000,
            'stationaryCarrierEpisodes': 0, 'longestStationaryCarrierMs': 1600}}
        with self.assertRaises(ValueError):
            compare(a, a)

    def test_fractional_count_rejected(self):
        a = sample()
        a['quality']['stallDiagnostics'] = {'nativeClock': {'fullTimeObserved': True, 'lastNativeMs': 300000,
            'error': None, 'wallGapCount': 0.5, 'longestWallGapSeconds': 3.5}}
        with self.assertRaises(ValueError):
            compare(a, a)


    def test_provenance_matching_fixture(self):
        a, b = sample(), sample()
        a.update(configSha256='a'*64, traceSha256='b'*64)
        b.update(configSha256='a'*64, traceSha256='c'*64)
        r = compare(a, b)
        self.assertTrue(r['provenance']['fixtureIdentityMatched'])
        self.assertTrue(r['provenance']['independentTraceEvidence'])
        self.assertFalse(r['causalImprovementVerified'])

    def test_provenance_missing_or_mismatched(self):
        a, b = sample(), sample()
        self.assertIsNone(compare(a, b)['provenance']['fixtureIdentityMatched'])
        a.update(configSha256='a'*64, traceSha256='b'*64)
        b.update(configSha256='c'*64, traceSha256='b'*64)
        r = compare(a, b)['provenance']
        self.assertFalse(r['fixtureIdentityMatched'])
        self.assertFalse(r['independentTraceEvidence'])

    def test_invalid_provenance(self):
        a = sample()
        a['configSha256'] = 'not-a-hash'
        with self.assertRaises(ValueError):
            compare(a, sample())
