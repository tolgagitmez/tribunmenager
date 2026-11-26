import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"integrations/league-soccer"))
from native_command_evidence import audit_frames,SLOTS
def fixture():
    values=dict(press=75,counter=50,support=50,width=50,tempo=80,formation=442)
    req=dict(team=0,revision=1,earliestMatchMs=100,values=values)
    players=[dict(team=0,databaseId=i+1,goalkeeper=False,formationTarget=[x/52.5,y/34,0]) for i,(x,y) in enumerate(SLOTS[442])]
    players.append(dict(team=0,databaseId=11,goalkeeper=True,formationTarget=[-1,0,0]))
    first=dict(engine="league-soccer",done=False,matchMs=100,elapsedMs=10,players=players,managerTactics=[dict(team=0,revision=0),dict(team=1,revision=0)])
    second=copy.deepcopy(first);second.update(matchMs=200,elapsedMs=20)
    second["managerTactics"][0]=dict(team=0,revision=1,appliedMatchMs=180,appliedElapsedMs=18,**values)
    final=copy.deepcopy(second);final.update(done=True,matchMs=5400000,elapsedMs=300000)
    return [first,second,final],[req]
class EvidenceTest(unittest.TestCase):
    def test_real_target_check_and_unobserved(self):
        frames,requests=fixture()
        r=audit_frames(frames,requests);self.assertTrue(r["allSubmittedObserved"]);self.assertTrue(r["acknowledgements"][0]["formationTargetsVerified"])
        frames[1]["players"][0]["formationTarget"][1]=0
        with self.assertRaises(ValueError):audit_frames(frames,requests)
        frames,requests=fixture();frames[2]["managerTactics"][0]={"team":0,"revision":0}
        with self.assertRaises(ValueError):audit_frames([frames[0],frames[1],frames[2]],requests)
        r=audit_frames([frames[0],frames[2]],requests);self.assertFalse(r["allSubmittedObserved"])
    def test_mutation_and_unknown_revision(self):
        frames,requests=fixture();frames[2]["managerTactics"][0]["press"]=1
        with self.assertRaises(ValueError):audit_frames(frames,requests)
        frames,requests=fixture()
        with self.assertRaises(ValueError):audit_frames(frames,[])
