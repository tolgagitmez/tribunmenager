import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_integration_gate import validate


def sample(paired=False):
    return {'passed': True, 'score': [1, 0], 'quality': {
        'football': {'score': [1, 0]}, 'errors': {},
        'presentation': {'nativeElapsedMs': 300000, 'checks': {'fiveMinuteWall': True, 'fullBrowserPlayback': True}},
        'offballLanes': {'evidenceAvailable': True, 'sampledSelections': {'primary': 3},
                         'invalidLines': 0, 'coordinationSamples': {'paired': 1} if paired else {}}}}


class GateTest(unittest.TestCase):
    def test_modes(self):
        self.assertTrue(validate(sample(), 'lanes')['passed'])
        self.assertTrue(validate(sample(True), 'coordinated')['passed'])
        self.assertFalse(validate(sample(), 'coordinated')['passed'])
        self.assertFalse(validate(sample(True), 'lanes')['passed'])

    def test_missing_or_failed_diagnostics(self):
        r = sample(True)
        r['quality']['errors']['actionExecution'] = 'ValueError'
        self.assertFalse(validate(r, 'coordinated')['passed'])
        self.assertFalse(validate({'passed': True}, 'lanes')['passed'])

    def test_clock_and_score(self):
        r = sample()
        r['quality']['presentation']['nativeElapsedMs'] = 299990
        r['quality']['football']['score'] = [0, 0]
        checks = validate(r, 'lanes')['checks']
        self.assertFalse(checks['fiveMinuteClock'])
        self.assertFalse(checks['completeFootballEvidence'])

    def test_never_claim_production_quality(self):
        r = validate(sample(True), 'coordinated')
        self.assertTrue(r['passed'])
        self.assertFalse(r['productionQualified'])
        self.assertFalse(r['subjectiveQualityVerified'])
