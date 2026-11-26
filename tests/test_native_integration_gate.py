import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_integration_gate import validate, REQUIRED_DIAGNOSTICS


def sample(paired=False):
    report = {'passed': True, 'score': [1, 0], 'quality': {
        'football': {'score': [1, 0]}, 'errors': {},
        'presentation': {'nativeElapsedMs': 300000, 'checks': {'fiveMinuteWall': True, 'fullBrowserPlayback': True}},
        'offballLanes': {'evidenceAvailable': True, 'sampledSelections': {'primary': 3},
                         'invalidLines': 0, 'coordinationSamples': {'paired': 1} if paired else {}}}}
    for name in REQUIRED_DIAGNOSTICS:
        report['quality'].setdefault(name, {})
    report['quality']['stallDiagnostics'] = {'carrier': {}}
    report['quality']['dribbleControl'] = {'touches': {}, 'separation': {}}
    return report


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

    def test_missing_parser_without_exception(self):
        r = sample()
        r['quality']['skeletonMotion'] = None
        r['quality']['dribbleControl']['touches'] = None
        result = validate(r, 'lanes')
        self.assertFalse(result['passed'])
        self.assertEqual(result['missingDiagnostics'], ['skeletonMotion', 'dribbleControl.touches'])

    def test_invalid_score_and_counts(self):
        r = sample()
        del r['score']
        del r['quality']['football']['score']
        self.assertFalse(validate(r, 'lanes')['checks']['completeFootballEvidence'])
        r = sample(True)
        r['quality']['offballLanes']['coordinationSamples'] = {'paired': True}
        self.assertFalse(validate(r, 'coordinated')['checks']['modeEvidence'])
        r['quality']['offballLanes']['sampledSelections'] = {'primary': 3, 'secondary': -1}
        self.assertFalse(validate(r, 'coordinated')['checks']['laneEvidence'])

    def test_invalid_shapes(self):
        self.assertFalse(validate([], 'lanes')['passed'])
        r = sample()
        r['quality']['offballLanes'] = 'wrong'
        self.assertFalse(validate(r, 'lanes')['passed'])
        r = sample()
        r['quality']['offballLanes']['coordinationSamples'] = None
        self.assertFalse(validate(r, 'lanes')['checks']['modeEvidence'])
        with self.assertRaises(ValueError):
            validate(sample(), 'unknown')
