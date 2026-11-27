import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integrations/league-soccer'))
from native_duration_comparison import read_match, compare, SHORT, LONG


def write_trace(path,duration,seed=2026,truncate=False,skip_half=False):
    Path(str(path)+'.fixture.json').write_text(json.dumps(dict(seed=seed,teams=[{},{}])))
    with path.open('w') as f:
        for t in range(0,duration+1,200):
            if truncate and t==duration or skip_half and t==duration//2:
                continue
            n=t//60000
            row=dict(schema=1,engine='league-soccer',elapsedMs=1000+t,
                matchMs=t*(5400000//duration),done=t==duration,
                fixedClock=dict(started=True,startMs=1000,elapsedMs=t,
                    half=t>=duration//2,finished=t==duration),
                inPlay=True,attackDirection=[1,-1],ball=[40 if (t//200)%2 else 37,0,0],
                players=[dict(team=0,uniquePossession=True),dict(team=1,uniquePossession=False)],
                score=[n//5,0],stats=dict(shots=[n,0],onTarget=[n//2,0],passes=[n*4,0],
                    completed=[n*3,0],fouls=[0,0]))
            f.write(json.dumps(row)+'\n')


class NativeDurationComparisonTest(unittest.TestCase):
    def test_matched_duration_and_rates(self):
        with tempfile.TemporaryDirectory() as d:
            short,long=Path(d)/'short',Path(d)/'long'
            write_trace(short,SHORT)
            write_trace(long,LONG)
            r=compare(short,long)
            self.assertEqual(r['short']['totals']['shots'],5)
            self.assertEqual(r['long']['totals']['shots'],30)
            self.assertEqual(r['totalDelta']['shots'],25)
            self.assertEqual(r['rateDeltaPerSimulationMinute']['shots'],0)
            self.assertGreater(r['long']['totals']['controlledBoxCrossings'],0)
            self.assertEqual(r['seed'],2026)

    def test_fixture_mismatch(self):
        with tempfile.TemporaryDirectory() as d:
            a,b=Path(d)/'a',Path(d)/'b'
            write_trace(a,SHORT)
            write_trace(b,LONG,seed=2027)
            with self.assertRaisesRegex(ValueError,'fixture or seed'):
                compare(a,b)

    def test_truncated_match(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'trace'
            write_trace(path,SHORT,truncate=True)
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                read_match(path,SHORT)

    def test_missing_halftime(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'trace'
            write_trace(path,SHORT,skip_half=True)
            with self.assertRaisesRegex(ValueError,'Incomplete'):
                read_match(path,SHORT)

    def test_wrong_duration(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'trace'
            write_trace(path,SHORT)
            with self.assertRaisesRegex(ValueError,'clock'):
                read_match(path,LONG)


if __name__=='__main__':
    unittest.main()
