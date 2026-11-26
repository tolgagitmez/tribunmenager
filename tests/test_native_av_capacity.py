import importlib.util
from pathlib import Path
import tempfile
import json
import unittest

spec = importlib.util.spec_from_file_location('capacity', Path(__file__).resolve().parents[1] / 'integrations/league-soccer/native-av-capacity.py')
capacity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capacity)

class CapacityTest(unittest.TestCase):
    def match(self, identity, start=10, end=310, passed=True):
        return dict(passed=passed, fixtureSha256=identity, kickoff=start, final=end)

    def test_all_matches_overlap_and_are_distinct(self):
        self.assertTrue(capacity.summarize([self.match(str(i), 10+i) for i in range(16)])['passed'])
        self.assertFalse(capacity.summarize([self.match('a'), self.match('b', 26)])['passed'])
        self.assertFalse(capacity.summarize([self.match('a'), self.match('a')])['passed'])
        self.assertFalse(capacity.summarize([self.match('a'), self.match('b', passed=False)])['passed'])
        self.assertFalse(capacity.summarize([])['passed'])

    def test_unique_fixtures_and_reproducible_seeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('balanced', 'counter-possession', 'possession-counter'):
                (root / (name + '.json')).write_text(json.dumps({'seed': 1, 'name': name}))
            names = capacity.prepare_fixtures(root, root / 'out', 16)
            self.assertEqual(len(names), 16)
            self.assertEqual([capacity.read(root / 'out' / (name + '.json'))['seed'] for name in names], list(range(12400, 12416)))

    def test_resource_percentile_and_minima(self):
        rows = [dict(cpuBusyPercent=i, availableMemoryMiB=100-i, freeDiskMiB=200-i) for i in range(1,21)]
        self.assertEqual(capacity.resource_summary(rows), dict(cpuP95Percent=19, minimumAvailableMemoryMiB=80, minimumFreeDiskMiB=180))
        self.assertIsNone(capacity.resource_summary([])['cpuP95Percent'])

if __name__ == '__main__':
    unittest.main()
