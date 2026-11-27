import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_stall_diagnostics import inspect_trace,ClockObserver
def row(t,x=0,phase=1,play=True,done=False):
    return dict(fixedClock=dict(started=True,elapsedMs=t),matchMs=t*18,phaseCode=phase,
        inPlay=play,setPiece=False,ballRetainerId=None,done=done,humanGamers=[0,0],
        ball=[x,0,.1],ballVelocity=[0,0,0],players=[dict(team=0,id=7,goalkeeper=False,uniquePossession=True,position=[x,0,0],velocity=[0,0,0])])
class StallTest(unittest.TestCase):
    def inspect(self,rows):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'match.ndjson';p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            return inspect_trace(p)
    def test_stationary_and_movement(self):
        r=self.inspect([row(t) for t in range(0,1400,100)]+[row(1400,1)])
        self.assertEqual(r['stationaryCarrierEpisodes'],1)
        self.assertEqual(r['longestStationaryCarrierMs'],1300)
        self.assertEqual(r['episodes'][0]['endReason'],'carrier-or-position-changed')
    def test_phase_stoppage_and_gap(self):
        r=self.inspect([row(t) for t in range(0,800,100)]+[row(800,play=False)]+[row(t,phase=2) for t in range(900,1600,100)]+[row(2200,phase=2)])
        self.assertEqual(r['stationaryCarrierEpisodes'],0);self.assertEqual(r['excludedGapMs'],700)
    def test_wall_gap_not_carrier(self):
        o=ClockObserver();o.observe(0,False,0);o.observe(100,False,.1)
        o.observe(100,False,4);o.observe(200,False,4.5);o.observe(300000,True,5)
        r=o.report(20);self.assertEqual(r['wallGapCount'],1);self.assertEqual(r['wallGaps'][0]['lastNativeMs'],100);self.assertTrue(r['fullTimeObserved'])
    def test_partial_tail(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'match.ndjson';p.write_text(json.dumps(row(0))+'\n'+'{"partial":')
            o=ClockObserver();o.poll(p,0);o.poll(p,4)
            r=o.report(5);self.assertEqual(r['lastNativeMs'],0);self.assertEqual(r['wallGapCount'],1)
    def test_extended_stationary_episode(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'match.ndjson'
            rows=[row(n) for n in range(900000,902100,100)]
            for r in rows:
                r['matchMs']=r['fixedClock']['elapsedMs']*3
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            result=inspect_trace(p,1800000)
            self.assertEqual(result['longestStationaryCarrierMs'],2000)
            self.assertEqual(result['totalStationaryCarrierMs'],2000)
            self.assertEqual(result['longestEpisode']['startNativeMs'],900000)
            with self.assertRaises(ValueError):
                inspect_trace(p)
    def test_keeper_excluded(self):
        rows=[row(t) for t in range(0,2000,100)]
        for r in rows:r['players'][0]['goalkeeper']=True
        self.assertEqual(self.inspect(rows)['stationaryCarrierEpisodes'],0)
