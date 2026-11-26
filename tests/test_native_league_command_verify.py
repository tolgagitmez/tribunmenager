import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_league_command_verify import verify
from native_command_evidence import audit_frames
from test_native_command_evidence import fixture

class HistoryTest(unittest.TestCase):
    def check(self,frames,requests,submitted,formations):
        control=dict(requests=requests,submitted=submitted,applied=submitted,pending=[False,False],formations=formations,traceEvidence=audit_frames(frames,requests))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'trace';p.write_text(''.join(json.dumps(f)+'\n' for f in frames))
            self.assertTrue(verify(control,p)['verified'])
            control['traceEvidence']['allSubmittedObserved']=False
            with self.assertRaises(ValueError):verify(control,p)
    def test_two_revisions_one_side_and_no_other_commands(self):
        frames,requests=fixture()
        second=copy.deepcopy(frames[1]);second.update(matchMs=300,elapsedMs=30)
        values=dict(requests[0]['values'],press=55,formation=0)
        requests.append(dict(team=0,revision=2,earliestMatchMs=200,values=values))
        second['managerTactics'][0]=dict(team=0,revision=2,appliedMatchMs=250,appliedElapsedMs=25,**dict(values,formation=442))
        frames[-1]['managerTactics']=copy.deepcopy(second['managerTactics'])
        frames.insert(2,second)
        self.check(frames,requests,[2,0],[442,0])
    def test_zero_commands(self):
        frames,_=fixture()
        for f in frames:f['managerTactics']=[dict(team=0,revision=0),dict(team=1,revision=0)]
        self.check(frames,[],[0,0],[0,0])
