import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
import unittest
from native_attack_intensity import attack_intensity


def sample():
    return dict(observedOpenPlayMs=120000, controlledMs=[50000,40000],
                controlledFinalThirdMs=[20000,10000], controlledBoxMs=[5000,2000],
                sameCarrierMs=[30000,20000], controlledForwardMeters=[60,20],
                controlledBackwardMeters=[15,30], controlledBoxCrossings=[4,2],
                observedBoxCrossings=[5,4])


class AttackIntensityTest(unittest.TestCase):
    def test_rates(self):
        result = attack_intensity(sample())
        self.assertEqual(result['finalThirdShareOfControlledPercent'], [40,25])
        self.assertEqual(result['boxShareOfControlledPercent'], [10,5])
        self.assertEqual(result['entriesPerObservedOpenPlayMinute'], [2,1])
        self.assertEqual(result['netForwardMetersPerSameCarrierMinute'], [90,-30])

    def test_missing(self):
        self.assertIsNone(attack_intensity(None))
        s = sample()
        s['controlledMs'][1] = s['controlledFinalThirdMs'][1] = s['controlledBoxMs'][1] = s['sameCarrierMs'][1] = 0
        s['controlledForwardMeters'][1] = s['controlledBackwardMeters'][1] = 0
        result = attack_intensity(s)
        self.assertIsNone(result['finalThirdShareOfControlledPercent'][1])
        self.assertIsNone(result['netForwardMetersPerSameCarrierMinute'][1])

    def test_inconsistent_times(self):
        s = sample()
        s['controlledMs'] = [80000,80000]
        with self.assertRaises(ValueError):
            attack_intensity(s)
        s = sample()
        s['controlledBoxMs'][0] = 25000
        with self.assertRaises(ValueError):
            attack_intensity(s)

    def test_invalid_values(self):
        for value in (float('nan'), -1, True):
            s = sample()
            s['controlledForwardMeters'][0] = value
            with self.assertRaises(ValueError):
                attack_intensity(s)

    def test_crossings(self):
        s = sample()
        s['controlledBoxCrossings'][0] = 6
        with self.assertRaises(ValueError):
            attack_intensity(s)

    def test_no_observation(self):
        s = {k: [0,0] for k in sample() if k != 'observedOpenPlayMs'}
        s['observedOpenPlayMs'] = 0
        result = attack_intensity(s)
        self.assertEqual(result['entriesPerObservedOpenPlayMinute'], [None,None])
        s['observedBoxCrossings'][0] = 1
        with self.assertRaises(ValueError):
            attack_intensity(s)
