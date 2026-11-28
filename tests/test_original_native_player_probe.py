import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from original_native_player_probe import validate_snapshot,parse_log

class NativePlayerProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/'db.sqlite'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE teams(id INT,name TEXT)')
            c.execute('CREATE TABLE players(id INT,team_id INT)')
            c.executemany('INSERT INTO teams VALUES(?,?)',[(1,'Home'),(2,'Away')])
            c.executemany('INSERT INTO players VALUES(?,?)',[(side*100+i,side) for side in (1,2) for i in range(1,12)])
        self.history=dict(homeTeam='Home',awayTeam='Away',homeGoals=2,awayGoals=0,nativeMatchClockMs=5400000)
        self.raw=dict(observationPoint='GameOverPage::Process',historySaved=True,nativeMatchClockMs=5400000,
            teams=[dict(side=side,nativeTeamId=side+1,score=2 if side==0 else 0,scorerIds=[101] if side==0 else [],
             players=[dict(nativePlayerId=(side+1)*100+i,rawCardCode=2 if i==1 else 0,
                          fatigueFactorInv=.75,activeAtFullTime=i!=1) for i in range(1,12)])
             for side in (0,1)])

    def test_independent_history_and_roster_checks(self):
        report=validate_snapshot(self.raw,self.history,self.db)
        home=report['teams'][0]
        self.assertEqual(home['goalsWithoutCreditedScorer'],1)
        self.assertEqual(home['players'][0]['goals'],1)
        self.assertEqual(home['players'][0]['yellow'],2)
        self.assertEqual(home['players'][0]['directRed'],0)
        self.assertIsNone(home['players'][0]['playedClockMs'])
        self.assertIsNone(home['players'][0]['assists'])
        self.assertFalse(report['productionImportAllowed'])
        for field,value in [('nativeTeamId',2),('score',1),('scorerIds',[999]),('scorerIds',[101]*3)]:
            bad=copy.deepcopy(self.raw)
            bad['teams'][0][field]=value
            with self.assertRaises(ValueError):
                validate_snapshot(bad,self.history,self.db)
        bad=copy.deepcopy(self.raw);bad['teams'][0]['players'][0]['rawCardCode']=5
        with self.assertRaises(ValueError):
            validate_snapshot(bad,self.history,self.db)

    def test_one_successful_debugger_record_required(self):
        line='TRIBUN_NATIVE_PLAYER_SNAPSHOT '+json.dumps(self.raw)
        self.assertEqual(parse_log('other\n'+line+'\n'),self.raw)
        for text in ('',line+'\n'+line,line+'\nTRIBUN_NATIVE_PLAYER_ERROR invalid'):
            with self.assertRaises(ValueError):
                parse_log(text)

if __name__=='__main__':
    unittest.main()
