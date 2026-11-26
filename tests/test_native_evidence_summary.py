import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations/league-soccer'))
from native_evidence_summary import CHECKS, summarize


class EvidenceSummaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write(self, path, value):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding='utf-8')

    def profile(self, directory, file, mode, failed=()):
        self.write(file, {'mode': mode, 'passed': not failed,
                         'checks': {key: key not in failed for key in CHECKS}})
        self.write(directory + '/alpha-1/match/private-beta-report.json',
                   {'quality': {'offballLanes': {
                       'sampledSelections': {'primary': 3},
                       'coordinationSamples': {'paired': 0}, 'invalidLines': 0}}})

    def test_stage209_failure(self):
        self.profile('alpha-state', 'baseline-evidence.json', 'lanes')
        self.profile('coordinated-state', 'coordinated-evidence.json', 'coordinated',
                     ('laneEvidence', 'modeEvidence'))
        self.write('attack-comparison.json', {'baseline': {'shots': 2},
                   'experimental': {'shots': 1}, 'provenance': {'fixtureIdentityMatched': False}})
        summary, notices = summarize(self.root, {'GATE_OUTCOME': 'failure'})
        self.assertEqual(len(notices), 1)
        self.assertIn('laneEvidence, modeEvidence', notices[0])
        self.assertIn('| shots | 2 | 1 |', summary)
        self.assertIn('Fixture identity matched: **no**', summary)

    def test_missing_and_ambiguous_reports(self):
        self.profile('alpha-state', 'baseline-evidence.json', 'lanes')
        self.write('alpha-state/alpha-2/match/private-beta-report.json', {})
        summary, notices = summarize(self.root, {})
        self.assertIn('report count=2', notices[0])
        self.assertIn('report count=0', notices[1])
        self.assertIn('Comparison report missing', summary)
        self.assertIn('| lanes | unknown | unknown | unknown | unknown | unknown |', summary)

    def test_invalid_json_and_no_untrusted_text(self):
        (self.root / 'baseline-evidence.json').write_text('{')
        self.write('coordinated-evidence.json', {'mode': 'coordinated',
                   'checks': {'evil\n::error::injected': False}})
        summary, notices = summarize(self.root, {'BUILD_OUTCOME': '<script>'})
        self.assertNotIn('injected', summary + str(notices))
        self.assertNotIn('<script>', summary)
        self.assertIn('missing/unreadable', summary)

    def test_success(self):
        self.profile('alpha-state', 'baseline-evidence.json', 'lanes')
        self.profile('coordinated-state', 'coordinated-evidence.json', 'coordinated')
        self.write('attack-comparison.json', {})
        summary, notices = summarize(self.root, {'GATE_OUTCOME': 'success'})
        self.assertEqual(notices, [])
        self.assertIn('Strict gate: **success**', summary)


if __name__ == '__main__':
    unittest.main()
