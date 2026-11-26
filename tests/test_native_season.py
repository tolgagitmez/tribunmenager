import sqlite3
import unittest
import native_season as n
import season_state

def fixture():
    teams=[{"team":t,"players":[{"nativeId":t*11+i+1,"rosterId":i,"rosterUid":f"club-{t}-{i}","startFitness":95} for i in range(11)]} for t in (0,1)]
    rows=[{"databaseId":t*11+i+1,"team":t,"active":True,"cardCode":0,"nominalMs":5400000,"activeMs":300000,"sprintMs":60000,"fatigueFactor":.84} for t in (0,1) for i in range(11)]
    rows[0].update(active=False,cardCode=2,nominalMs=1800000,activeMs=100000,sprintMs=20000)
    rows[11].update(active=False,cardCode=4,nominalMs=3600000,activeMs=200000,sprintMs=40000)
    return {"engine":"league-soccer","done":True,"matchMs":5400000,"score":[2,1],"participation":rows},{"schema":1,"teams":teams}

class NativeSeasonTest(unittest.TestCase):
    def test_card_codes_and_stable_identity(self):
        f,m=fixture()
        s=n.candidate(f,m)
        self.assertEqual(s["cards"],[2,1])
        self.assertEqual(s["reds"],[1,1])
        self.assertEqual(s["appearances"][0]["minutes"],30)
        self.assertEqual(s["appearances"][0]["rosterUid"],"club-0-0")
        self.assertEqual(n.decode_cards(3),(0,True))
        self.assertEqual(len(n.preview(s)),22)

    def test_existing_season_writer_idempotent_and_suspends(self):
        f,m=fixture()
        s=n.candidate(f,m)
        with sqlite3.connect(":memory:") as db:
            db.row_factory=sqlite3.Row
            db.executescript(season_state.SCHEMA)
            key=("TEST",2,3,5)
            season_state.apply_fixture(db,key,s["appearances"])
            season_state.apply_fixture(db,key,s["appearances"])
            row=db.execute("SELECT * FROM season_player_state WHERE slot=3 AND player_key='uid:club-0-0'").fetchone()
            self.assertEqual(row["appearances"],1)
            self.assertEqual(row["minutes"],30)
            self.assertEqual(row["suspension_until_round"],4)
            self.assertAlmostEqual(row["fitness"],89.67)
            self.assertEqual(db.execute("SELECT count(*) FROM season_fixture_appearances").fetchone()[0],22)

    def test_stage104_recompute_sidecar_and_reject_corruption(self):
        f,m=fixture()
        s=n.candidate(f,m);s["seasonPreview"]=n.preview(s)
        self.assertEqual(n.verify_report(f,m,s)["score"],[2,1])
        s["appearances"][0]["rosterUid"]="other"
        with self.assertRaises(ValueError):n.verify_report(f,m,s)

    def test_stage104_identity_and_bench_guards(self):
        f,m=fixture();m["teams"][1]["team"]=0
        with self.assertRaises(ValueError):n.candidate(f,m)
        f,m=fixture();m["teams"][0]["players"][1]["rosterId"]=0
        with self.assertRaises(ValueError):n.candidate(f,m)
        f,m=fixture();f["participation"][0]["databaseId"]=True
        with self.assertRaises(ValueError):n.candidate(f,m)
        f,m=fixture();m["teams"][0]["bench"]=[dict(nativeId=23,rosterId=11,rosterUid="bench",startFitness=95)]
        f["participation"].append(dict(databaseId=23,team=0,active=True,cardCode=0,nominalMs=60000,activeMs=1000,sprintMs=0,fatigueFactor=.99))
        with self.assertRaises(ValueError):n.candidate(f,m)

    def test_incomplete_or_corrupt_data_rejected(self):
        for mutate in (lambda f:f["participation"].pop(),
                       lambda f:f["participation"][1].update(databaseId=1),
                       lambda f:f["participation"][1].update(sprintMs=999999),
                       lambda f:f["participation"][1].update(cardCode=9),
                       lambda f:f["participation"][0].update(active=True),
                       lambda f:f.update(done=False)):
            f,m=fixture()
            mutate(f)
            with self.assertRaises(ValueError):n.candidate(f,m)

if __name__=="__main__":unittest.main()
