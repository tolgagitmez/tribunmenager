import copy
import unittest
from original_native_player_timeline import reconstruct

class NativeTimelineTests(unittest.TestCase):
    def setUp(self):
        self.keys=[dict(side=s,nativePlayerId=i) for s in (0,1) for i in range(1,13)]
        first=[k for k in self.keys if k['nativePlayerId']<=11]
        second=[k for k in first if k!={'side':0,'nativePlayerId':1}]
        second.append(dict(side=0,nativePlayerId=12))
        self.final=dict(nativeMatchClockMs=5520000,teams=[
            dict(players=[dict(nativePlayerId=i,fatigueFactorInv=.72,
                               activeAtFullTime=dict(side=s,nativePlayerId=i) in second)
                          for i in range(1,13)]) for s in (0,1)])
        self.events=[dict(kind='period',period=1,active=first,
                          fatigue=[dict(k,fatigueFactorInv=1.) for k in self.keys]),
                     dict(kind='deactivate',period=1,clockMs=1800000,side=0,nativePlayerId=1),
                     dict(kind='activate',period=1,clockMs=1800000,side=0,nativePlayerId=12),
                     dict(kind='period',period=2,previousClockMs=2820000,active=second),
                     dict(kind='final',clockMs=5520000)]

    def test_period_reset_preserves_added_time(self):
        r=reconstruct(self.events,self.final)
        by={(p['side'],p['nativePlayerId']):p for p in r['players']}
        self.assertEqual(r['observedMatchClockExposureMs'],5640000)
        self.assertEqual(by[0,1]['observedOnPitchMinutes'],30)
        self.assertEqual(by[0,12]['observedOnPitchMinutes'],64)
        self.assertEqual(by[1,1]['observedOnPitchMinutes'],94)
        self.assertEqual(by[1,12]['observedOnPitchMinutes'],0)
        self.assertAlmostEqual(by[1,1]['fatigueFactorInvDelta'],-.28)
        self.assertIsNone(by[0,1]['assists'])
        self.assertFalse(r['officialMinutesVerified'])

    def test_missing_transition_or_wrong_clock_rejected(self):
        variants=[self.events[:1]+self.events[2:],self.events[:-1],
                  self.events[:3]+[dict(self.events[3],previousClockMs=2699999)]+self.events[4:]]
        for events in variants:
            with self.assertRaises(ValueError):
                reconstruct(events,self.final)
        bad=copy.deepcopy(self.final)
        bad['teams'][1]['players'][0]['activeAtFullTime']=False
        with self.assertRaisesRegex(ValueError,'Unobserved'):
            reconstruct(self.events,bad)


    def test_regulation_end_sentinel_preserves_second_half_added_time(self):
        final=copy.deepcopy(self.final)
        final['nativeMatchClockMs']=5400000
        events=copy.deepcopy(self.events)
        events[-1].update(regulationEndReset=True,historyClockMs=5400000)
        report=reconstruct(events,final)
        self.assertEqual(report['periodEndClockMs'],[2820000,5520000])
        self.assertEqual(report['observedMatchClockExposureMs'],5640000)
        self.assertTrue(report['regulationEndResetObserved'])
        for clock in (5399999,5400001):
            bad=copy.deepcopy(events)
            bad[-1]['historyClockMs']=clock
            with self.assertRaises(ValueError):
                reconstruct(bad,final)
