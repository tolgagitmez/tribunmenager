import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from original_held_trial_dispatch import review_digest,held_fixture,dispatch_held_trial

class HeldTrialTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/'web.sqlite'
        self.review=dict(league='TEST',round=1,home=0,away=1,kickoff=100,
            nativeFixtureId=12,homeTeamId=20,awayTeamId=30,nativeDate='2026-06-01',
            managedTeamId=20,snapshotId='snapshot-'+'a'*32,saveName='League',saveSha256='b'*64)
        with sqlite3.connect(self.db) as c:
            c.executescript("""
                CREATE TABLE fixtures(league TEXT,round INT,home INT,away INT,kickoff REAL,home_score INT,away_score INT);
                CREATE TABLE native_fixture_holds(league TEXT,round INT,home INT,away INT,kickoff REAL,review_sha256 TEXT);
                CREATE TABLE live_matches(league TEXT,round INT,home INT,away INT);
                INSERT INTO fixtures VALUES('TEST',1,0,1,100,NULL,NULL);
            """)
            c.execute("INSERT INTO native_fixture_holds VALUES('TEST',1,0,1,100,?)",(review_digest(self.review),))

    def test_gate_and_single_dispatch_boundary(self):
        self.assertEqual(held_fixture(self.db,self.review,99)[1],'not-due')
        self.assertEqual(held_fixture(self.db,dict(self.review,saveSha256='c'*64),100)[1],'reviewed-hold-mismatch')
        before=self.db.read_bytes()
        with patch('original_held_trial_dispatch.probe_due',side_effect=[
            dict(claimed=True,nativeMenuKickoffProbePassed=True),
            dict(claimed=False,reason='already-reserved')]) as probe:
            with self.assertRaises(ValueError):
                dispatch_held_trial(self.db,self.root,None,None,{},self.review,now=100)
            early=dispatch_held_trial(self.db,self.root,None,None,{},self.review,experimental=True,now=99)
            self.assertFalse(early['claimed'])
            probe.assert_not_called()
            first=dispatch_held_trial(self.db,self.root,None,None,{},self.review,experimental=True,now=100)
            self.assertTrue(first['claimed'])
            self.assertTrue(first['webHoldMatched'])
            self.assertFalse(first['scoreWritten'])
            self.assertFalse(first['matchCompleted'])
            second=dispatch_held_trial(self.db,self.root,None,None,{},self.review,experimental=True,now=101)
            self.assertEqual(second['reason'],'already-reserved')
        self.assertEqual(self.db.read_bytes(),before)

    def test_prior_round_and_legacy_conflict(self):
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO fixtures VALUES('TEST',0,0,1,90,NULL,NULL)")
        self.assertEqual(held_fixture(self.db,self.review,100)[1],'prior-round-unfinished')
        with sqlite3.connect(self.db) as c:
            c.execute("INSERT INTO live_matches VALUES('TEST',1,0,1)")
        self.assertEqual(held_fixture(self.db,self.review,100)[1],'legacy-worker-conflict')


    def test_full_match_option_forwarded_only_after_hold_gate(self):
        bundle=self.root/'reviewed-halftime.json'
        with patch('original_held_trial_dispatch.probe_due',return_value=dict(
            claimed=True,matchCompleted=True,privateResultStaged=True)) as probe:
            early=dispatch_held_trial(self.db,self.root,None,None,{},self.review,
                experimental=True,now=99,halftime_bundle=bundle)
            self.assertFalse(early['claimed'])
            probe.assert_not_called()
            result=dispatch_held_trial(self.db,self.root,None,None,{},self.review,
                experimental=True,now=100,halftime_bundle=bundle)
            self.assertTrue(result['matchCompleted'])
            self.assertTrue(result['privateResultStaged'])
            self.assertFalse(result['automaticProductionKickoff'])
            self.assertFalse(result['scoreWritten'])
            self.assertEqual(probe.call_args.kwargs,{'halftime_bundle':bundle})
