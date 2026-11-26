import json,sys,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]/"integrations/league-soccer"
sys.path.insert(0,str(HERE))
from native_roster import plan_from_config,roster_snapshot,verify_halftime
class RosterTest(unittest.TestCase):
    def test_plan_and_projection(self):
        config={"players":[{"id":i} for i in range(12)],"starters":list(range(11)),"nativeSubstitutions":[[{"out":1,"in":11}],[]]}
        plans=plan_from_config(config)
        self.assertEqual(plans,[{"team":0,"out":2,"in":23}])
        meta=[{"nativeId":2,"team":0,"reserve":False,"name":"Starter"},{"nativeId":23,"team":0,"reserve":True,"name":"Reserve"}]
        frame={"matchMs":2800000,"participation":[dict(team=0,databaseId=2,active=False,nominalMs=2700000,fatigueFactor=.7,injuryLevel=.2,cardCode=1),dict(team=0,databaseId=23,active=True,nominalMs=100000,fatigueFactor=.99,injuryLevel=0,cardCode=0)]}
        result=roster_snapshot(frame,meta,plans,0)
        self.assertTrue(result["available"]);self.assertEqual(result["changes"][0]["state"],"observed")
        self.assertEqual(result["players"][0]["injuryLevel"],.2)
        frame["participation"][0]["injuryLevel"]=2
        self.assertFalse(roster_snapshot(frame,meta,plans,0)["available"])
        self.assertFalse(roster_snapshot({},meta,plans,0)["available"])
    def test_audit_rejects_early_or_missing_switch(self):
        manifest={"teams":[{"team":0,"players":[{"nativeId":1,"rosterId":11}],"bench":[{"nativeId":23,"rosterId":12}],"substitutions":[{"out":1,"in":23}]},{"team":1,"players":[{"nativeId":12,"rosterId":10}],"bench":[]}]}
        season={"done":True,"score":[0,0],"substitutions":[{"team":0,"out":11,"in":12,"performed":True}]}
        def frame(minute,ident,done=False):
            return {"engine":"league-soccer","humanGamers":[0,0],"matchMs":minute,"fixedClock":{"started":True},"players":[{"databaseId":ident,"team":0},{"databaseId":12,"team":1}],"done":done,"score":[0,0],"participation":[{"injuryLevel":0}]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);m=p/"manifest";s=p/"season";t=p/"trace"
            m.write_text(json.dumps(manifest));s.write_text(json.dumps(season))
            def check(frames):
                t.write_text("\n".join(map(json.dumps,frames))+"\n");return verify_halftime(t,m,s)
            self.assertTrue(check([frame(0,1),frame(2700000,23),frame(5400000,23,True)])["allPlannedChangesObserved"])
            for frames in ([frame(0,1),frame(2600000,23),frame(5400000,23,True)],[frame(0,1),frame(5400000,1,True)],[frame(0,1),frame(2700000,23),frame(5400000,1,True)]):
                with self.assertRaises(ValueError):check(frames)
