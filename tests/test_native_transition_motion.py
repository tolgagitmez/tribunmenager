import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_transition_motion import inspect_transitions

def row(t,v,phase=1,play=True):
    return dict(fixedClock=dict(started=True,elapsedMs=t),matchMs=t*18,phaseCode=phase,
        inPlay=play,setPiece=False,done=False,humanGamers=[0,0],ball=[0,0,0],
        players=[dict(team=0,id=7,goalkeeper=False,position=[5,0,0],velocity=v)])

class TransitionMotionTest(unittest.TestCase):
    def read(self,rows):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'match.ndjson'
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            return inspect_transitions(p)
    def test_transitions(self):
        r=self.read([row(0,[1,0,0]),row(100,[2,0,0]),row(200,[0,2,0]),row(300,[0,1,0])])
        self.assertEqual(r['intervals'],3)
        self.assertEqual(r['accelerationIntervals'],1)
        self.assertEqual(r['brakingIntervals'],1)
        self.assertEqual(r['sharpTurnIntervals'],1)
        self.assertEqual(r['maxSampledTurnDegrees'],90)
    def test_gaps_and_stops(self):
        r=self.read([row(0,[1,0,0]),row(300,[2,0,0]),row(400,[0,2,0],phase=2),
            row(500,[1,0,0],phase=2,play=False),row(600,[2,0,0],phase=2)])
        self.assertEqual(r['intervals'],0)
        self.assertEqual(r['excludedFramePairs'],2)
    def test_near_ball_excluded(self):
        rows=[row(0,[1,0,0]),row(100,[2,0,0])]
        rows[1]['players'][0]['position']=[1,0,0]
        self.assertEqual(self.read(rows)['intervals'],0)
