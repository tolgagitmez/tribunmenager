import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_dribble_diagnostics import inspect_dribble

def row(t,d=1):
    return dict(fixedClock=dict(started=True,elapsedMs=t),matchMs=t*18,phaseCode=1,
        inPlay=True,setPiece=False,done=False,humanGamers=[0,0],ballRetainerId=None,
        ball=[d,0,.1],players=[dict(team=0,id=7,goalkeeper=False,uniquePossession=True,position=[0,0,0])])

class DribbleDiagnosticsTest(unittest.TestCase):
    def read(self,lines,rows):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'game.log';p.write_text(lines)
            trace=Path(d)/'match.ndjson';trace.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            return inspect_dribble(p,trace)
    def test_launch_modes(self):
        p='[tribun-dribble-control] phase=1 match_ms=1800 team=0 player=7 enabled=1 before=5 after=4 projected=2 clearance=3 proposed=0.8\n'
        r=self.read(p+p.replace('enabled=1','enabled=0').replace('after=4','after=5')+p.replace('after=4','after=3'),[])
        self.assertEqual(r['touches']['groups']['experimental']['appliedReduction'],1)
        self.assertEqual(r['touches']['groups']['baseline']['appliedReduction'],0)
        self.assertEqual(r['touches']['groups']['baseline']['proposedReduction'],1)
        self.assertEqual(r['touches']['invalidLines'],1)
    def test_separation_and_duplicate(self):
        r=self.read('',[row(0,.5),row(100,1.5),row(100,10),row(200,2.5)])
        self.assertEqual(r['separation']['samples'],3)
        self.assertEqual(r['separation']['over1_25m'],2)
        self.assertEqual(r['separation']['over2m'],1)
        self.assertEqual(r['separation']['meanPlanarDistanceM'],1.5)
    def test_excluded_ball_and_keeper(self):
        a,b,c=row(0),row(100),row(200)
        a['ball'][2]=1
        b['players'][0]['goalkeeper']=True
        c['setPiece']=True
        self.assertEqual(self.read('',[a,b,c])['separation']['samples'],0)
