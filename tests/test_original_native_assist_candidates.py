import copy
import unittest
from original_native_assist_candidates import analyze

class AssistCandidatesTests(unittest.TestCase):
    def setUp(self):
        self.roster=[{1,2,3},{4,5,6}]
        def event(kind,clock,passes=(0,0),shots=(0,0),score=(0,0),scorers=((),()),period=1,**kw):
            return dict(kind=kind,clockMs=clock,period=period,passes=list(passes),
                        shots=list(shots),score=list(score),scorers=[list(v) for v in scorers],**kw)
        self.event=event
        self.events=[event('period',0),event('touch',60000,side=0,nativePlayerId=1,touchType=0),
            event('touch',61000,passes=(1,0),side=0,nativePlayerId=2,touchType=1),
            event('touch',62000,passes=(1,0),side=0,nativePlayerId=2,touchType=0),
            event('reset',63000,passes=(1,0),shots=(1,0),score=(1,0),scorers=((2,),())),
            event('period',2700000,passes=(1,0),shots=(1,0),score=(1,0),scorers=((2,),()),period=2),
            event('final',5400000,passes=(1,0),shots=(1,0),score=(1,0),scorers=((2,),()),period=2)]
        self.history=dict(nativeMatchClockMs=5400000,homeGoals=1,awayGoals=0,passAttempts=[1,0],shots=[1,0])

    def test_uninterrupted_pass_and_shot(self):
        report=analyze(self.events,self.history,self.roster)
        self.assertEqual(report['assistCandidates'],1)
        self.assertEqual(report['goals'][0]['assistCandidateId'],1)
        self.assertFalse(report['officialAssistsVerified'])
        self.assertFalse(report['productionImportAllowed'])

    def test_opponent_touch_reset_own_goal_and_time_limit(self):
        for interruption in [
            self.event('touch',61500,passes=(1,0),side=1,nativePlayerId=4,touchType=2),
            self.event('reset',61500,passes=(1,0))]:
            events=self.events[:3]+[interruption]+self.events[3:]
            self.assertEqual(analyze(events,self.history,self.roster)['assistCandidates'],0)
        own=copy.deepcopy(self.events)
        for e in own[4:]:
            e['scorers']=[[],[]]
        self.assertIsNone(analyze(own,self.history,self.roster)['goals'][0]['scorerId'])
        slow=copy.deepcopy(self.events)
        slow[3]['clockMs']=190000
        slow[4]['clockMs']=191000
        self.assertEqual(analyze(slow,self.history,self.roster)['assistCandidates'],0)

    def test_counter_and_identity_mismatch(self):
        bad=copy.deepcopy(self.events);bad[-1]['passes']=[2,0]
        with self.assertRaises(ValueError):
            analyze(bad,self.history,self.roster)
        bad=copy.deepcopy(self.events);bad[1]['nativePlayerId']=999
        with self.assertRaises(ValueError):
            analyze(bad,self.history,self.roster)


    def test_missing_or_invalid_second_half_boundary(self):
        for bad in (
            self.events[:5]+[dict(self.events[5],kind='reset')]+self.events[6:],
            self.events[:5]+[dict(self.events[5],clockMs=0)]+self.events[6:],
            self.events[:5]+[self.events[5],self.events[5]]+self.events[6:],
        ):
            with self.assertRaises(ValueError):
                analyze(bad,self.history,self.roster)
        self.assertTrue(analyze(self.events,self.history,self.roster)['nativeFinalCountersMatched'])
