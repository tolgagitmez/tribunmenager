import copy
import sqlite3
import tempfile
import unittest
from pathlib import Path
from original_player_evidence import roster_baseline,identity_map,validate_observations,FIELDS

class PlayerEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'roster.sqlite'
        with sqlite3.connect(self.path) as db:
            db.execute('CREATE TABLE players(id INT,team_id INT,firstname TEXT,lastname TEXT,formationorder INT)')
            db.executemany('INSERT INTO players VALUES(?,?,?,?,?)',[
                (team*100+i,team,'Same','Name',i) for team in (1,2) for i in range(1,13)])
        self.baseline=roster_baseline(self.path,dict(homeTeamId=1,awayTeamId=2))
        self.rosters=[[dict(id=i,uid=f'{side}-{i}') for i in range(1,13)] for side in (0,1)]
        self.reviewed=[dict(side=side,nativePlayerId=(side+1)*100+i,webPlayerKey=f'uid:{side}-{i}')
                       for side in (0,1) for i in range(1,13)]
        self.mapped=identity_map(self.baseline,self.reviewed,self.rosters)
        self.history=dict(nativeMatchClockMs=5400000,homeGoals=2,awayGoals=1)
        self.report=dict(revision=self.baseline['revision'],sourceSaveSha256=self.baseline['sourceSaveSha256'],
            players=[dict(side=side,nativePlayerId=pid,**dict.fromkeys(FIELDS)) for side,pid in self.mapped])

    def test_readonly_and_explicit_unavailable_values(self):
        self.assertEqual(len(self.mapped),24)
        self.assertEqual(sum(p['savedStarter'] for t in self.baseline['teams'] for p in t['players']),22)
        self.assertFalse(self.baseline['liveLineupVerified'])
        result=validate_observations(self.baseline,self.mapped,self.report,self.history)
        self.assertEqual(result['missingCounts'],dict.fromkeys(FIELDS,24))
        self.assertTrue(all(r['goals'] is None for r in result['players']))
        self.assertFalse(result['productionImportAllowed'])

    def test_reject_missing_or_duplicate_mapping(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            identity_map(self.baseline,self.reviewed[:-1],self.rosters)
        bad=copy.deepcopy(self.reviewed)
        bad[1]['webPlayerKey']=bad[0]['webPlayerKey']
        with self.assertRaisesRegex(ValueError,'duplicate'):
            identity_map(self.baseline,bad,self.rosters)

    def test_observation_conservation_and_identity(self):
        candidate=copy.deepcopy(self.report)
        candidate['players'][0].update(goals=2,assists=0,playedClockMs=5400000,yellow=1,red=0,fatigueFactorInv=.73)
        result=validate_observations(self.baseline,self.mapped,candidate,self.history)
        self.assertEqual(result['players'][0]['goals'],2)
        self.assertFalse(result['sourceAuthenticityVerified'])
        self.assertFalse(result['nativeFatigueIsWebFitness'])
        for field,value in [('goals',3),('assists',3),('playedClockMs',5400001),('yellow',3),('fatigueFactorInv',73)]:
            bad=copy.deepcopy(candidate)
            bad['players'][0][field]=value
            with self.assertRaises(ValueError):
                validate_observations(self.baseline,self.mapped,bad,self.history)
        bad=copy.deepcopy(candidate)
        del bad['players'][0]['red']
        with self.assertRaisesRegex(ValueError,'explicit null'):
            validate_observations(self.baseline,self.mapped,bad,self.history)
        bad=copy.deepcopy(candidate)
        bad['players'][1]=bad['players'][0]
        with self.assertRaisesRegex(ValueError,'duplicate'):
            validate_observations(self.baseline,self.mapped,bad,self.history)
        bad=copy.deepcopy(candidate)
        for row in bad['players'][:12]:
            row['playedClockMs']=5400000
        with self.assertRaisesRegex(ValueError,'eleven-player'):
            validate_observations(self.baseline,self.mapped,bad,self.history)


    def test_first_half_added_time_retained_in_conservation(self):
        candidate=copy.deepcopy(self.report)
        candidate['periodEndClockMs']=[2820000,5400000]
        candidate['players'][0]['playedClockMs']=5520000
        result=validate_observations(self.baseline,self.mapped,candidate,self.history)
        self.assertEqual(result['observedClockLimitMs'],5520000)
        self.assertEqual(result['players'][0]['playedClockMs'],5520000)
        for ends in ([2699999,5400000],[2820000,5400001],[3600001,5400000],['2820000',5400000]):
            bad=copy.deepcopy(candidate)
            bad['periodEndClockMs']=ends
            with self.assertRaisesRegex(ValueError,'period end'):
                validate_observations(self.baseline,self.mapped,bad,self.history)
        bad=copy.deepcopy(candidate)
        for row in bad['players'][:12]:
            row['playedClockMs']=5520000
        with self.assertRaisesRegex(ValueError,'eleven-player'):
            validate_observations(self.baseline,self.mapped,bad,self.history)
