import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integrations/league-soccer'))
from native_playback_schedule import schedule, RATES, SOURCE_MS, TARGET_MS


def manifest(parts):
    start = 0
    totals = dict.fromkeys(RATES, 0)
    rows = []
    for level, duration in parts:
        rows.append(dict(startMs=start,endMs=start+duration,level=level,reasons=[level]))
        totals[level] += duration
        start += duration
    return dict(schema=1,simulationMs=SOURCE_MS,levelDurationsMs=totals,
                score=[2,1],segments=rows)


def standard():
    return manifest([('routine',660000),('critical',60000),('build-up',300000),
                     ('dangerous',120000),('routine',660000)])


class PlaybackScheduleTest(unittest.TestCase):
    def test_exact_budget_and_critical_speed(self):
        result = schedule(standard())
        self.assertTrue(result['targetFeasible'])
        self.assertEqual(result['plannedPlaybackMs'], TARGET_MS)
        self.assertEqual(result['deviationMs'],0)
        self.assertEqual(result['score'],[2,1])
        self.assertTrue(result['criticalAtNormalSpeed'])
        self.assertEqual(result['playbackDurationsMs']['critical'],60000)
        self.assertGreater(result['playbackDurationsMs']['dangerous'],30000)

    def test_continuous_source_and_playback(self):
        result=schedule(standard())
        rows=result['segments']
        self.assertEqual(rows[0]['sourceStartMs'],0)
        self.assertEqual(rows[0]['playbackStartMs'],0)
        self.assertEqual(rows[-1]['sourceEndMs'],SOURCE_MS)
        self.assertEqual(rows[-1]['playbackEndMs'],TARGET_MS)
        for a,b in zip(rows,rows[1:]):
            self.assertEqual(a['sourceEndMs'],b['sourceStartMs'])
            self.assertEqual(a['playbackEndMs'],b['playbackStartMs'])
        for s in rows:
            lo,hi=RATES[s['level']]
            self.assertGreaterEqual(s['speed'],lo)
            self.assertLessEqual(s['speed'],hi)
            self.assertEqual(s['speed'],(s['sourceEndMs']-s['sourceStartMs'])/
                             (s['playbackEndMs']-s['playbackStartMs']))

    def test_impossible_short_budget_keeps_critical(self):
        r=schedule(manifest([('critical',600000),('routine',1200000)]))
        self.assertFalse(r['targetFeasible'])
        self.assertEqual(r['status'],'target-too-short')
        self.assertEqual(r['plannedPlaybackMs'],700000)
        self.assertEqual(r['playbackDurationsMs']['critical'],600000)

    def test_impossible_long_budget(self):
        r=schedule(manifest([('routine',SOURCE_MS)]),target_ms=600000)
        self.assertFalse(r['targetFeasible'])
        self.assertEqual(r['status'],'target-too-long')
        self.assertEqual(r['plannedPlaybackMs'],450000)

    def test_equal_priority_sharing(self):
        r=schedule(manifest([('dangerous',60000),('routine',1680000),('dangerous',60000)]))
        a,b=r['segments'][0],r['segments'][-1]
        self.assertLessEqual(abs((a['playbackEndMs']-a['playbackStartMs'])-
                                 (b['playbackEndMs']-b['playbackStartMs'])),1)

    def test_invalid_timeline(self):
        h=standard()
        for change in ('gap','overlap','truncated','bad-level','bad-totals'):
            m=copy.deepcopy(h)
            if change=='gap': m['segments'][1]['startMs']+=1000
            elif change=='overlap': m['segments'][1]['startMs']-=1000
            elif change=='truncated': m['segments'].pop()
            elif change=='bad-level': m['segments'][0]['level']='unknown'
            else: m['levelDurationsMs']['routine']+=1000
            with self.subTest(change=change),self.assertRaises(ValueError):
                schedule(m)

    def test_integer_rounding_at_many_boundaries(self):
        h=manifest([('routine',1000)]*1500+[('dangerous',1000)]*250+
                   [('critical',1000)]*50)
        r=schedule(h)
        self.assertEqual(r['plannedPlaybackMs'],TARGET_MS)
        self.assertTrue(r['targetFeasible'])
        self.assertTrue(all(RATES[s['level']][0]<=s['speed']<=RATES[s['level']][1]
                            for s in r['segments']))

    def test_deterministic_and_no_input_mutation(self):
        h=standard()
        before=copy.deepcopy(h)
        self.assertEqual(schedule(h),schedule(h))
        self.assertEqual(h,before)


if __name__=='__main__':
    unittest.main()
