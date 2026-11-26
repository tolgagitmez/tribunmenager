from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_playback_optimize import optimize
from native_playback_schedule import RATES, SOURCE_MS, schedule


def manifest(parts):
    totals=dict.fromkeys(RATES,0)
    start=0
    segments=[]
    for level,duration,reason in parts:
        segments.append(dict(startMs=start,endMs=start+duration,level=level,reasons=[reason]))
        totals[level]+=duration
        start+=duration
    return dict(schema=1,simulationMs=SOURCE_MS,levelDurationsMs=totals,score=[1,0],segments=segments)


class PlaybackOptimizationTest(unittest.TestCase):
    def test_shoulder_reduces_jump(self):
        m=manifest([('routine',870000,'possession'),('critical',60000,'goal'),
                    ('routine',870000,'restart')])
        result=optimize(m)
        opt=result['optimization']
        self.assertTrue(result['targetFeasible'])
        self.assertEqual(result['plannedPlaybackMs'],300000)
        self.assertGreater(opt['shoulderSeconds'],0)
        self.assertLess(opt['after']['maximumJumpRatio'],opt['before']['maximumJumpRatio'])
        self.assertEqual(result['playbackDurationsMs']['critical'],60000)
        for row in result['segments']:
            if 'critical-transition-shoulder' in row['reasons']:
                self.assertGreaterEqual(row['speed'],3)
                self.assertLessEqual(row['speed'],4)

    def test_reason_only_blocks_coalesce(self):
        m=manifest([('routine',600000,'a'),('routine',600000,'b'),('routine',600000,'c')])
        result=optimize(m)
        self.assertEqual(len(result['segments']),1)
        self.assertEqual(result['sourceHighlightSegments'],m['segments'])

    def test_preserve_danger_and_duration(self):
        m=manifest([('routine',660000,'a'),('critical',60000,'shot'),
                    ('build-up',300000,'b'),('dangerous',120000,'box'),
                    ('routine',660000,'c')])
        r=optimize(m)
        self.assertEqual(r['plannedPlaybackMs'],300000)
        self.assertGreaterEqual(r['optimization']['originalDangerPlaybackMsAfter'],
                                r['optimization']['originalDangerPlaybackMsBefore']-1)
        self.assertEqual(r['score'],[1,0])
        for a,b in zip(r['segments'],r['segments'][1:]):
            self.assertEqual(a['sourceEndMs'],b['sourceStartMs'])
            self.assertEqual(a['playbackEndMs'],b['playbackStartMs'])

    def test_infeasible_keeps_critical(self):
        r=optimize(manifest([('critical',600000,'goal'),('routine',1200000,'a')]))
        self.assertFalse(r['targetFeasible'])
        self.assertEqual(r['plannedPlaybackMs'],700000)
        self.assertEqual(r['playbackDurationsMs']['critical'],600000)

    def test_cannot_weaken_critical_bounds(self):
        m=manifest([('critical',60000,'goal'),('routine',1740000,'a')])
        with self.assertRaises(ValueError):
            schedule(m,rate_limits={0:(1,2)})

    def test_deterministic(self):
        m=manifest([('critical',10000,'kickoff'),('routine',1790000,'a')])
        self.assertEqual(optimize(m),optimize(m))


if __name__=='__main__':
    unittest.main()
